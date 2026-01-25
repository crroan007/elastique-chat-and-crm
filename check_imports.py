
import sys
import os
import traceback

print("--- DIAGNOSTICS: CHECK IMPORTS ---")
print(f"CWD: {os.getcwd()}")

# 1. Setup Path
MUSE_TALK_PATH = os.path.abspath(os.path.join(os.getcwd(), 'external/MuseTalk'))
print(f"Adding MuseTalk Path: {MUSE_TALK_PATH}")
if os.path.exists(MUSE_TALK_PATH):
    print("Path Exists: YES")
    print(f"Contents of {MUSE_TALK_PATH}: {os.listdir(MUSE_TALK_PATH)}")
else:
    print("Path Exists: NO")

sys.path.append(MUSE_TALK_PATH)
print("sys.path updated.")

# 2. Try Improvements
try:
    print("Attempting: import musetalk")
    import musetalk
    print(f"SUCCESS: musetalk imported from {musetalk.__file__}")
except Exception as e:
    print(f"FAILURE importing musetalk: {e}")
    traceback.print_exc()

try:
    print("Attempting: from musetalk.utils.blending import get_image")
    from musetalk.utils.blending import get_image
    print("SUCCESS: get_image imported")
except Exception as e:
    print(f"FAILURE importing get_image: {e}")
    traceback.print_exc()

try:
    print("Attempting: from musetalk.utils.utils import load_all_model")
    from musetalk.utils.utils import load_all_model
    print("SUCCESS: load_all_model imported")
except Exception as e:
    print(f"FAILURE importing load_all_model: {e}")
    traceback.print_exc()

try:
    import diffusers
    print(f"SUCCESS: diffusers imported. Version: {diffusers.__version__}")
except Exception as e:
    print(f"FAILURE importing diffusers: {e}")
