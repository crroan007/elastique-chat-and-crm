import asyncio
import io
import sys
import numpy as np
import edge_tts
import av
from pipecat.services.ai_services import TTSService

from pipecat.frames.frames import (
    Frame,
    AudioRawFrame,
    # ImageFrame, # Removed
    TextFrame,
    StartFrame,
    StartFrame,
    EndFrame
)
# Custom Frame for Telemetry
class DebugFrame(Frame):
    def __init__(self, trace_id: str, event: str, data: dict = None):
        super().__init__()
        self.trace_id = trace_id
        self.event = event
        self.data = data or {}
    def __str__(self):
        return f"DebugFrame({self.event}, {self.data})"

from pipecat.processors.frame_processor import FrameProcessor

from typing import AsyncGenerator, Optional

# sys path for dynamic imports
sys.path.append("c:/Homebrew Apps/Elastique - GPT_chatbot")
# Note: We will import MuseTalkBridge dynamically to avoid init issues if dependencies aren't loaded yet.

class VideoFrame(Frame):
    def __init__(self, image: bytes, size: tuple, format: str):
        super().__init__()
        self.image = image
        self.size = size
        self.format = format
    def __str__(self):
        return f"VideoFrame(size={self.size}, format={self.format})"

class ElastiqueTTSService(FrameProcessor):
    """
    Wraps EdgeTTS for Pipecat.
    Stream's audio bytes directly into Pipecat's pipeline.
    """
    def __init__(self, voice="en-US-AvaNeural", rate="+0%", pitch="+0Hz", **kwargs):
        super().__init__(**kwargs)
        self._voice = voice
        self._rate = rate
        self._pitch = pitch

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        # Internal helper (still generator)
        print(f"DEBUG: ElastiqueTTSService run_tts: {text}")
        communicate = edge_tts.Communicate(text, self._voice, rate=self._rate, pitch=self._pitch)
        
        mp3_buffer = io.BytesIO()
        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_buffer.write(chunk["data"])
            print("DEBUG: EdgeTTS Stream Complete, decoding...")
        except Exception as e:
            print(f"DEBUG: EdgeTTS Stream Error: {e}")
            return 
        
        mp3_buffer.seek(0)
        try:
            container = av.open(mp3_buffer)
            stream = container.streams.audio[0]
            
            # Resampler to force s16le (16-bit PCM) @ 24kHz (or keep original rate)
            # This fixes "staticky" audio if source is fltp (float)
            resampler = av.AudioResampler(format='s16', layout='mono', rate=stream.sample_rate)

            for frame in container.decode(stream):
                # Resample frame to s16
                for resampled_frame in resampler.resample(frame):
                    pcm_bytes = resampled_frame.to_ndarray().tobytes()
                    # print(f"DEBUG: Audio Frame: {resampled_frame.format.name} {resampled_frame.rate}Hz len={len(pcm_bytes)}", flush=True)
                    
                    af = AudioRawFrame(
                        audio=pcm_bytes, 
                        sample_rate=resampled_frame.rate, 
                        num_channels=len(resampled_frame.layout.channels)
                    )
                    import uuid
                    af.id = str(uuid.uuid4())
                    yield af
        except Exception as e:
            print(f"TTS Decoding Error: {e}")
            pass

    async def process_frame(self, frame, direction):
        # Debug Trace
        print(f"DEBUG: TTS ENTRY type: {type(frame)}")
        if isinstance(frame, TextFrame):
            print(f"DEBUG: TTS process_frame received TextFrame: {frame.text}", flush=True)
            
            # Telemetry: Start TTS
            await self.push_frame(DebugFrame("system", "TTS_START", {"text_len": len(frame.text)}), direction)
            
            start_time = asyncio.get_event_loop().time()
            async for audio_frame in self.run_tts(frame.text):
                print(f"DEBUG: TTS Generated Audio -> Pushing to {self._next}", flush=True)
                await self.push_frame(audio_frame, direction)
            
            # Telemetry: End TTS
            duration = asyncio.get_event_loop().time() - start_time
            await self.push_frame(DebugFrame("system", "TTS_END", {"duration_sec": duration}), direction)
            
        elif isinstance(frame, (AudioRawFrame, VideoFrame)) or type(frame).__name__ in ['AudioRawFrame', 'VideoFrame']:
            print(f"DEBUG: TTS Passthrough {type(frame).__name__} -> Pushing to {self._next}", flush=True)
            if self._next:
                try:
                    print(f"DEBUG: Force Calling {self._next}.process_frame ID:{id(self._next)}", flush=True)
                    await self._next.process_frame(frame, direction)
                    print("DEBUG: Force Call Returned", flush=True)
                except Exception as e:
                    print(f"DEBUG: Force Call Error: {e}", flush=True)
            else:
                await self.push_frame(frame, direction)
        else:
            await super().process_frame(frame, direction)

from pipecat.processors.frame_processor import FrameProcessor

class MuseTalkVideoService(FrameProcessor):
    """
    Custom Service to handle Video Generation.
    """
    def __init__(self, bridge_instance):
        super().__init__()
        self.bridge = bridge_instance
        self.idle_loop_frames = [] # Load from mp4
        print(f"DEBUG: MuseTalkVideoService INITIALIZED ID:{id(self)}", flush=True)

    async def process_frame(self, frame, direction):
        # Debug Entry
        # print(f"DEBUG: MuseTalk ENTRY type: {type(frame)} ID:{id(self)}", flush=True) 
        # raise Exception("MUSETALK_IS_WATCHING_YOU") # Start with print, enable crash if desperate
 
        if isinstance(frame, AudioRawFrame) or type(frame).__name__ == 'AudioRawFrame':
            # print(f"DEBUG: MuseTalk handling AudioRawFrame detected.", flush=True)
            
            # --- PERFECT SYNC CHANGE ---
            # DO NOT pass audio through immediately.
            # We wait for video generation to pair them.
            
            # We have audio. We need to generate lip-sync frames.
            audio_bytes = frame.audio
            
            if self.bridge:
                 try:
                     # Offload Inference to Thread to UNBLOCK LOOP 
                     import asyncio
                     
                     # Wrapper to run generator to completion
                     def run_inference_batch():
                         # Bridge now yields (video_frame, audio_slice) tuples
                         return list(self.bridge.generate_stream_batch(audio_bytes))

                     # Result is a list of (video, audio) tuples
                     import time
                     t0 = time.time()
                     
                     # Telemetry: Start
                     await self.manual_push_frame(DebugFrame("system", "INFERENCE_START", {"audio_bytes": len(audio_bytes)}), direction)
                     
                     generated_batch = await asyncio.to_thread(run_inference_batch)
                     
                     dt = time.time() - t0
                     count = len(generated_batch)
                     
                     # Telemetry: End
                     await self.manual_push_frame(DebugFrame("system", "INFERENCE_COMPLETE", {"duration_sec": dt, "frames": count}), direction)
                     
                     for video_array, audio_slice in generated_batch:
                         import cv2
                         try:
                            # 1. Prepare Audio Frame
                            # Create new AudioRawFrame with limits
                            af = AudioRawFrame(
                                audio=audio_slice,
                                sample_rate=24000, # MuseTalk native
                                num_channels=1
                            )
                            import uuid
                            af.id = str(uuid.uuid4()) # Unique ID
                            
                            # 2. Prepare Video Frame
                            ret, buffer = cv2.imencode('.jpg', video_array)
                            if ret:
                                jpg_bytes = buffer.tobytes()
                                vf = VideoFrame(image=jpg_bytes, size=(256, 256), format="JPEG")
                                vf.transport_destination = None
                                
                                # 3. ATOMIC PUSH (Audio THEN Video)
                                # Emitting them sequentially ensures the player receives them 
                                # as a coupled event.
                                await self.manual_push_frame(af, direction)
                                await self.manual_push_frame(vf, direction)
                                
                         except Exception as e:
                            print(f"Frame encoding error: {e}")
                 except Exception as e:
                     print(f"Bridge Stream Error: {e}")

            else:
                 # Local Fallback (No Bridge) - Still need to pass audio!
                 # Pass original frame in fallback mode
                 await self.manual_push_frame(frame, direction)
                 try:
                     with open("static/img/sarah_v2.png", "rb") as f:
                         static_jpg = f.read()
                     
                     num_audio_samples = len(audio_bytes) 
                     duration_sec = (num_audio_samples / 2) / 24000.0
                     num_video_frames = int(duration_sec * 25)
                     if num_video_frames < 1: num_video_frames = 1

                     for _ in range(num_video_frames):
                         vf = VideoFrame(image=static_jpg, size=(256, 256), format="JPEG")
                         vf.transport_destination = None 
                         await self.manual_push_frame(vf, direction)

                 except Exception as e:
                     print(f"Fallback generation error: {e}")

        else:
            # Universal Pass-Through via Manual Push
            await self.manual_push_frame(frame, direction)
            
            if isinstance(frame, StartFrame):
                print("DEBUG: MuseTalk MANUAL StartFrame Handling...", flush=True)
                self._start_frame = frame
                # Trigger Idle Frame with slight delay to ensure Pipeline State is ready
                import asyncio
                # DISABLE SERVER SIDE IDLE FRAME: Causing pipeline instability/race conditions.
                # using Client-Side Init instead.
                # asyncio.create_task(self.emit_idle_frame_safe())
            
            # print(f"DEBUG: MuseTalk PushFrame {type(frame)}", flush=True)

    async def emit_idle_frame_safe(self):
        import asyncio
        await asyncio.sleep(0.5) # Wait for pipeline to settle
        await self.emit_idle_frame()



    async def emit_idle_frame(self):
        """
        Sends a single static frame (Idle state) to the transport.
        Crucial for showing the avatar before user speaks.
        """
        print("DEBUG: Emitting Idle Frame...")
        try:
            import cv2
            jpg_bytes = None
            
            # Try to get from bridge cache first (best quality)
            if self.bridge and self.bridge.avatar_cache:
                frame = self.bridge.avatar_cache["frame"]
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    jpg_bytes = buffer.tobytes()
            
            # Fallback to file
            if not jpg_bytes:
                with open("static/img/sarah_v2.png", "rb") as f:
                    jpg_bytes = f.read()
            
            if jpg_bytes:
                vf = VideoFrame(image=jpg_bytes, size=(256, 256), format="JPEG")
                # Use None for direction if FrameDirection is missing
                await self.push_frame(vf, None)
                print("DEBUG: Idle Frame Emitted.")
                
        except Exception as e:
             print(f"Idle Frame Error: {e}")

    async def manual_push_frame(self, frame, direction):
        if not hasattr(frame, "transport_destination"):
             try:
                 frame.transport_destination = None
             except:
                 pass
        if not hasattr(frame, "pts"):
             try:
                 frame.pts = 0
             except:
                 pass
        
        if self._next:
             await self._next.process_frame(frame, direction)

