import sys
import os
import numpy as np
import time

# Add root to path
sys.path.append(os.getcwd())

from services.musetalk_bridge_v2 import MuseTalkBridge

def test_bridge_isolation():
    print("--- DOE MODULE TEST: MuseTalk Bridge Isolation ---")
    
    # 1. Initialization
    print("[1/4] Initializing Bridge...")
    try:
        bridge = MuseTalkBridge()
    except Exception as e:
        print(f"FAIL: Init crashed. {e}")
        return

    # 2. Asset Loading
    print("[2/4] Loading Avatar (Sarah V2)...")
    avatar_path = "static/img/sarah_v2.png"
    if not os.path.exists(avatar_path):
        print(f"FAIL: Avatar not found at {avatar_path}")
        return
    
    bridge.load_avatar(avatar_path)
    if not bridge.avatar_cache:
        print("FAIL: Avatar failed to cache.")
        return
    # Check if fallback mode
    if bridge.face_parser is None:
        print("WARN: Running in Fast Paste Mode (No FaceParsing).")
    print("PASS: Avatar Loaded.")

    # 3. Audio Synthesis (Dummy PCM)
    print("[3/4] Synthesizing Dummy Audio (1s, 24kHz, Mono, Int16)...")
    sample_rate = 24000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # Generate a 440Hz sine wave (just to have signal)
    audio_data = (0.5 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    audio_bytes = audio_data.tobytes()
    print(f"Audio Size: {len(audio_bytes)} bytes")

    # 4. Inference Stream
    print("[4/4] Executing Inference Stream...")
    start_time = time.time()
    frame_count = 0
    
    try:
        # Batch size 4 default in code
        generator = bridge.generate_stream_batch(audio_bytes, batch_size=4)
        
        for frame in generator:
            frame_count += 1
            if frame_count == 1:
                print(f" > First Frame Received. Shape: {frame.shape}, Dtype: {frame.dtype}")
                if frame.shape != (256, 256, 3):
                    print(f"FAIL: Unexpected frame shape {frame.shape}")
            
            # Print dot every 5 frames
            if frame_count % 5 == 0:
                print(".", end="", flush=True)
                
        print("\nStream Complete.")
        
    except Exception as e:
        print(f"\nFAIL: Inference Crashed. {e}")
        import traceback
        traceback.print_exc()
        return

    elapsed = time.time() - start_time
    print(f"\nStats: {frame_count} frames in {elapsed:.2f}s ({frame_count/elapsed:.1f} FPS)")
    
    expected_frames = 25 # 1s * 25fps
    if frame_count >= 20: # Allow some tolerance
        print("RESULT: PASS")
    else:
        print(f"RESULT: FAIL (Expected ~25 frames, got {frame_count})")

if __name__ == "__main__":
    test_bridge_isolation()
