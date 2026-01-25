import asyncio
import websockets
import json
import time

async def verify_pipeline():
    uri = "ws://localhost:8001/ws/chat"
    print(f"CONNECTING to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("CONNECTED.")
            
            # Send Init
            init_msg = {"type": "text", "content": "Init"}
            await websocket.send(json.dumps(init_msg))
            print("SENT: Init")
            
            start_time = time.time()
            audio_frames = 0
            video_frames = 0
            
            while time.time() - start_time < 20:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    if isinstance(message, bytes):
                        try:
                            data = json.loads(message.decode('utf-8'))
                        except:
                             print(f"RECEIVED: Binary {len(message)} bytes")
                             continue
                    else:
                        # Handle Text Frame (String)
                        try:
                            data = json.loads(message)
                        except:
                            print(f"RECEIVED: String {message[:50]}")
                            continue
                    
                    # Process Parsed JSON
                    msg_type = data.get("type")
                    if msg_type == "audio":
                        audio_frames += 1
                        print(f"RECEIVED: Audio Frame")
                    elif msg_type == "video":
                        video_frames += 1
                        print(f"RECEIVED: Video Frame (Size: {len(data['content'])})")
                    elif msg_type == "text":
                        print(f"RECEIVED: Text - {data['content']}")
                        
                except asyncio.TimeoutError:
                    print("... Waiting ...")
                    continue
                except websockets.exceptions.ConnectionClosed as e:
                    print(f"CONNECTION CLOSED: Code {e.code}, Reason: {e.reason}")
                    break
            
            print("--- REPORT ---")
            print(f"Audio Frames: {audio_frames}")
            print(f"Video Frames: {video_frames}")
            
            if audio_frames > 0 and video_frames > 0:
                print("RESULT: PASS")
            else:
                print("RESULT: FAIL")

    except Exception as e:
        print(f"FATAL ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(verify_pipeline())
