import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8001/ws/chat"

    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            
            # Send Init
            msg = {"type": "text", "content": "Hello Sarah, debug mode."}
            print(f"Sending: {msg}")
            await websocket.send(json.dumps(msg))
            
            # Receive Loop
            while True:
                try:
                    # Give plenty of time for TTS/Video generation
                    response = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                    print(f"Received: {response}")
                    data = json.loads(response)
                    if data.get("type") == "text":
                        print(f"Text: {data.get('content')}")
                except asyncio.TimeoutError:
                    print("Timeout waiting for response.")
                    break
                except websockets.exceptions.ConnectionClosed:
                    print("Connection Closed by Server.")
                    break
    except Exception as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
