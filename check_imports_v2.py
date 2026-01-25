
import sys
import os
import traceback

print("--- DIAGNOSTICS V2: GET_IMAGE ---")
MUSE_TALK_PATH = os.path.abspath(os.path.join(os.getcwd(), 'external/MuseTalk'))
sys.path.append(MUSE_TALK_PATH)

try:
    print("Importing musetalk.utils.blending...")
    import musetalk.utils.blending
    print(f"Module imported: {musetalk.utils.blending}")
    print(f"Attributes: {dir(musetalk.utils.blending)}")
    
    print("Importing get_image directly...")
    from musetalk.utils.blending import get_image
    print("SUCCESS: get_image imported")
except Exception as e:
    print(f"FAILURE: {e}")
    traceback.print_exc()
