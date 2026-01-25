
import os
import sys

MUSE_TALK_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'external/MuseTalk'))
sys.path.append(MUSE_TALK_PATH)

class ContextGuard:
    def __init__(self, target_dir):
        self.target_dir = target_dir
        self.original_dir = os.getcwd()
    def __enter__(self):
        os.chdir(self.target_dir)
        sys.path.append(self.target_dir) # Ensure path is active
    def __exit__(self, exc_type, exc_val, exc_tb):
        os.chdir(self.original_dir)
        if self.target_dir in sys.path:
             sys.path.remove(self.target_dir)

try:
    print(f"Adding {MUSE_TALK_PATH} to path")
    
    with ContextGuard(MUSE_TALK_PATH):
        print("Inside ContextGuard")
        print(f"CWD: {os.getcwd()}")
        
        # Test Import
        from transformers import WhisperModel
        print(f"WhisperModel: {WhisperModel}")
        
        # Test Local Variable Assignment
        w = WhisperModel
        print(f"Assigned: {w}")

    print("Outside ContextGuard")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
