import sys
import os
import asyncio
from unittest.mock import MagicMock

# Add root to path
sys.path.append(os.getcwd())

# Mock Pipecat stuff before importing wrappers
sys.modules["pipecat"] = MagicMock()
sys.modules["pipecat.processors"] = MagicMock()
sys.modules["pipecat.processors.frame_processor"] = MagicMock()
sys.modules["pipecat.frames"] = MagicMock()
sys.modules["pipecat.frames.frames"] = MagicMock()
sys.modules["pipecat.transports"] = MagicMock()
sys.modules["pipecat.transports.base_transport"] = MagicMock()

# Manually create the classes that wrappers inherit/use
class MockFrameProcessor:
    def __init__(self):
        self._next = None
    def add_downstream(self, ds):
        self._next = ds
    async def push_frame(self, frame, direction):
        if self._next:
             await self._next.process_frame(frame, direction)

class MockFrame:
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self, k, v)

# Inject classes into the mocks
sys.modules["pipecat.processors.frame_processor"].FrameProcessor = MockFrameProcessor
sys.modules["pipecat.frames.frames"].Frame = MockFrame
sys.modules["pipecat.frames.frames"].AudioRawFrame = MockFrame
sys.modules["pipecat.frames.frames"].VideoFrame = MockFrame
sys.modules["pipecat.frames.frames"].TextFrame = MockFrame
sys.modules["pipecat.frames.frames"].StartFrame = MockFrame
sys.modules["pipecat.frames.frames"].EndFrame = MockFrame
sys.modules["pipecat.frames.frames"].FrameDirection = MagicMock()

# Now import valid classes or mock them if heavily dependent
# We need to import the actual class to test it.
# But pipecat_wrappers imports real pipecat...
# Let's try to import and catch errors, or assume environment has pipecat installed?
# The user environment seems to have pipecat-ai installed.
try:
    from services.pipecat_wrappers import MuseTalkVideoService
    from pipecat.frames.frames import VideoFrame, AudioRawFrame, TextFrame, FrameDirection
except ImportError as e:
    print(f"FAIL: Import Error. {e}")
    sys.exit(1)

async def test_service_integration():
    print("--- DOE INTEGRATION TEST: MuseTalkVideoService ---")
    
    # 1. Instantiate
    print("[1/5] Instantiating Service with Mock Bridge...")
    mock_bridge = MagicMock()
    # Mock bridge.avatar_cache
    mock_bridge.avatar_cache = {
        "frame": MagicMock(), # numpy array mock
        "coords": (0,0,100,100),
        "latents": MagicMock()
    }
    
    try:
        service = MuseTalkVideoService(bridge_instance=mock_bridge)
        print("PASS: Instantiation.")
    except Exception as e:
        print(f"FAIL: Instantiation crashed. {e}")
        return

    # 2. Test Link (The previous crash point)
    print("[2/5] Testing .link() method...")
    mock_downstream = MagicMock()
    try:
        if not hasattr(service, 'link'):
             raise AttributeError("Method .link() is MISSING.")
        service.link(mock_downstream)
        print("PASS: .link() exists and runs.")
    except Exception as e:
        print(f"FAIL: .link() failed. {e}")
        return

    # 3. Test Idle Frame
    print("[3/5] Testing emit_idle_frame()...")
    # We need to mock manual_push_frame or push_frame because it calls self._next...
    # The class calls await self.push_frame(vf, FrameDirection.DOWNSTREAM)
    # We need to mock push_frame on the instance?
    # Or just let it hit the mock_downstream (since we called link, add_downstream was likely called).
    # But add_downstream is from FrameProcessor parent.
    # If FrameProcessor is real, it sets self._next.
    
    # Let's mock push_frame to verify it's called
    service.push_frame = MagicMock()
    future = asyncio.Future()
    future.set_result(None)
    service.push_frame.return_value = future

    try:
        await service.emit_idle_frame()
        print("PASS: emit_idle_frame executed.")
        # Verify call args?
        # service.push_frame.assert_called()
    except Exception as e:
        print(f"FAIL: emit_idle_frame crashed. {e}")
        return

    # 4. Test Process Frame (Audio -> Video)
    print("[4/5] Testing process_frame (Audio -> Video)...")
    mock_audio_frame = AudioRawFrame(audio=b'\x00'*100, sample_rate=24000, num_channels=1)
    
    # Mock bridge generator
    import numpy as np
    dummy_frame = np.zeros((256, 256, 3), dtype=np.uint8)
    mock_bridge.generate_stream_batch.return_value = [dummy_frame]
    
    # Needs manual_push_frame mock?
    service.manual_push_frame = MagicMock()
    service.manual_push_frame.return_value = future

    try:
        await service.process_frame(mock_audio_frame, FrameDirection.DOWNSTREAM)
        print("PASS: process_frame handled AudioRawFrame.")
    except Exception as e:
        print(f"FAIL: process_frame crashed. {e}")
        return

    print("--- INTEGRATION TEST SUCCESS ---")

if __name__ == "__main__":
    asyncio.run(test_service_integration())
