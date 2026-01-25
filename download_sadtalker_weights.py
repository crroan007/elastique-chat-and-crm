from huggingface_hub import snapshot_download
import os

def download_sadtalker_weights():
    print("Downloading SadTalker Weights...")
    
    # Main Checkpoints
    base_path = "SadTalker/checkpoints"
    os.makedirs(base_path, exist_ok=True)
    
    try:
        snapshot_download(
            repo_id="vinthony/SadTalker",
            local_dir=base_path,
            local_dir_use_symlinks=False
        )
        print("Success! SadTalker weights downloaded.")
        
        # We also need 'gfpgan' for enhancement if we use it, but optional for POC.
        
    except Exception as e:
        print(f"Error downloading weights: {e}")

if __name__ == "__main__":
    download_sadtalker_weights()
