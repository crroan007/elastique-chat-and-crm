import torch
import sys
import platform

def check_system():
    print("--- Visual Avatar Capability Check ---")
    print(f"OS: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version.split()[0]}")
    
    try:
        cuda_avail = torch.cuda.is_available()
        print(f"NVIDIA GPU Available (CUDA): {cuda_avail}")
        
        if cuda_avail:
            print(f"GPU Name: {torch.cuda.get_device_name(0)}")
        else:
            print("\n[WARNING] No NVIDIA GPU detected (or Drivers missing).")
            print("Visual Animation (SadTalker/Wav2Lip) relies heavily on GPU.")
            print("Running on CPU will take ~2-5 minutes per sentence.")
            
    except ImportError:
        print("PyTorch not installed. Cannot verify GPU.")

if __name__ == "__main__":
    check_system()
