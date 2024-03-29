import json
import websocket
import threading
import time
import requests
import subprocess
import os
import base64

# Replace these with the appropriate values for your setup
NODE_RPC_URL = "ws://localhost:27020/websocket"
QUERY = "tm.event='Tx'"
COMETBFT_RPC_URL = "http://localhost:27010/broadcast_tx_commit"
WORKING_DIRECTORY = "/Users/stefanoangieri/testing/bin/chain2"

def reconstruct_message(attributes):
    # Construct the message structure to match the MsgSendPacket message format
    message = {
        "body": {
            "messages": [
                {
                    "@type": "/ibc.core.channel.v1.MsgSendPacket",
                    "source_port": attributes["source_port"],
                    "source_channel": "channel-1",
                    "timeout_height": {
                        "revision_number": int(attributes["timeout_height"].split("-")[0]),  # Ensuring it's an integer
                        "revision_height": int(attributes["timeout_height"].split("-")[1]),  # Ensuring it's an integer
                    },
                    "timeout_timestamp": int(attributes["timeout_timestamp"]),  # Ensuring it's an integer
                    "packet": {
                        "sequence": int(attributes.get("sequence", 1)),  # Ensuring it's an integer
                        "source_port": attributes["source_port"],
                        "source_channel": "channel-1",
                        "destination_port": "transfer",  # Fill in destination port
                        "destination_channel": "channel-0",  # Fill in destination channel
                        "data": base64.b64encode(json.dumps(attributes["packet_data"]).encode()).decode(),  # Encoding data as base64
                        "timeout_height": {
                            "revision_number": int(attributes["timeout_height"].split("-")[0]),  # Ensuring it's an integer
                            "revision_height": int(attributes["timeout_height"].split("-")[1]),  # Ensuring it's an integer
                        }, 
                    "timeout_timestamp": int(attributes["timeout_timestamp"]),
                    },
                    "signer": "cosmos1vg6nqau0lu5yhkdh60v8saaqqtz0ect30estxe",  # Adjust signer if necessary
                }
            ],
            "memo": "",  # Fill in memo if necessary
            "timeout_height": "0",
            "extension_options": [],
            "non_critical_extension_options": [],
        },
        "auth_info": {
            "signer_infos": [],
            "fee": {
                "amount": [],
                "gas_limit": "200000",
                "payer": "",
                "granter": "",
            },
            "tip": None,
        },
        "signatures": [],
    }
    return message

def sign_message(cometbft_message):
    # Define file paths
    transaction_file = 'transfer.json'
    signed_transaction_file = 'signed.json'
    
    # Save the message to be signed in transfer.json
    with open(os.path.join(WORKING_DIRECTORY, transaction_file), 'w') as f:
        json.dump(cometbft_message, f)

    # Command to sign the transaction
    os.chdir(WORKING_DIRECTORY)
    cmd = f"simd tx sign {transaction_file} " \
          f"--from $VALIDATOR_CHAIN2 " \
          f"--chain-id chain2 " \
          f"--keyring-backend test " \
          f"--home ../../gm/chain2 " \
          f"--node tcp://localhost:27010 > {signed_transaction_file} "

    # Execute the command
    subprocess.run(cmd, shell=True)

    # Read the signed message
    with open(os.path.join(WORKING_DIRECTORY, signed_transaction_file), 'r') as f:
        signed_msg = json.load(f)

    # Encode the transaction
    encoded_transaction = encode_transaction(signed_msg)

    # Broadcast the encoded transaction
    broadcast_transaction(encoded_transaction)

    print("Signed message:", signed_msg)
    return signed_msg

def encode_transaction(transaction):
    # Encode the transaction using the provided command
    cmd = f"simd tx encode - --from=json <<< '{json.dumps(transaction)}'"
    encoded_transaction = subprocess.check_output(cmd, shell=True)
    return encoded_transaction.decode("utf-8")

def broadcast_transaction(encoded_transaction):
    # Broadcast the encoded transaction
    cmd = f"simd tx broadcast - --broadcast-mode async <<< '{encoded_transaction}'"
    subprocess.run(cmd, shell=True)

def on_message(ws, message):
    print("Received a message:")
    print(message)

    def forward_message(msg):
        try:
            msg_data = json.loads(msg)
            events = msg_data.get("result", {}).get("data", {}).get("value", {}).get("TxResult", {}).get("result", {}).get("events", [])

            for event in events:
                if event['type'] == 'send_packet':
                    attributes = {attr['key']: attr['value'] for attr in event['attributes']}
                    reconstructed_message = reconstruct_message(attributes)

                    print("------------")
                    print("Reconstructed Message:")
                    print(json.dumps(reconstructed_message, indent=2))
                    print("------------")

                    # Sign and broadcast the message
                    signed_msg = sign_message(reconstructed_message)

                    # Send the signed message to CometBFT RPC
                    response = requests.post(COMETBFT_RPC_URL, json=signed_msg)
                    print("Message forwarded to CometBFT:", response.status_code, response.text)
        except Exception as e:
            print(f"Error processing message: {e}")

    threading.Thread(target=forward_message, args=(message,)).start()

def on_error(ws, error):
    print("WebSocket error:", error)

def on_close(ws, close_status_code, close_msg):
    print("### WebSocket closed ###")

def on_open(ws):
    def run(*args):
        subscribe_message = {
            "jsonrpc": "2.0",
            "method": "subscribe",
            "id": "0",
            "params": {"query": QUERY}
        }
        ws.send(json.dumps(subscribe_message))
    threading.Thread(target=run).start()

if __name__ == "__main__":
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp(NODE_RPC_URL,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()
