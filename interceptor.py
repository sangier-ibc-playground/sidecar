import json
import websocket
import threading
import time

# Replace these with the appropriate values for your setup
NODE_RPC_URL = "ws://localhost:27020/websocket"
QUERY = "tm.event='Tx'"
COMETBFT_RPC_URL = "http://localhost:27010/broadcast_tx_commit"  # Adjust the port if necessary

def on_message(ws, message):
    print("Received a message:")
    print("-------------")
    print(message)
    print("-------------")

    def forward_message(msg):
        try:
            msg_data = json.loads(msg)
            print("Decoded Message Data:")
            print(msg_data)
            print("-------------")

            # Correcting the path to extract events
            events = msg_data.get("result", {}).get("data", {}).get("value", {}).get("TxResult", {}).get("result", {}).get("events", [])
            
            print("Events Extracted:")
            print(events)
            print("-------------")

            if not events:
                print("No events found in the message.")
                return

            # Find the send_packet event
            for event in events:
                if event['type'] == 'send_packet':
                    attributes = {attr['key']: attr['value'] for attr in event['attributes']}
                    source_port = attributes.get("source_port")
                    source_channel = attributes.get("source_channel")
                    timeout_height = attributes.get("timeout_height")
                    timeout_timestamp = attributes.get("timeout_timestamp")
                    packet_data = attributes.get("packet_data")

                    # Output the extracted details
                    print(f"Source port: {source_port}, Source channel: {source_channel}")
                    print(f"Timeout height: {timeout_height}, Timeout timestamp: {timeout_timestamp}")
                    print(f"Packet data: {packet_data}")
                    break
            else:
                print("send_packet event not found in the message.")

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")

    threading.Thread(target=forward_message, args=(message,)).start()

def on_error(ws, error):
    print(error)

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")

def on_open(ws):
    def run(*args):
        subscribe_message = {
            "jsonrpc": "2.0",
            "method": "subscribe",
            "id": "0",
            "params": {
                "query": QUERY
            }
        }
        ws.send(json.dumps(subscribe_message))
        while True:
            time.sleep(1)
    threading.Thread(target=run).start()

if __name__ == "__main__":
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp(NODE_RPC_URL,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)

    ws.run_forever()
