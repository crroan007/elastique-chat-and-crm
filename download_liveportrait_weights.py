from huggingface_hub import snapshot_download
import os

def download_weights():
    print("Downloading LivePortrait Weights from HuggingFace...")
    # Target directory inside LivePortrait folder
    base_path = "LivePortrait/pretrained_weights"
    
    # Ensure directory exists
    os.makedirs(base_path, exist_ok=True)
    
    try:
        # Download the main weights
        snapshot_download(
            repo_id="KwaiVGI/LivePortrait",
            local_dir=base_path,
            local_dir_use_symlinks=False
        )
        print("Success! Weights downloaded.")
        
        # Also need detailed InsightFace models if not included, but usually LivePortrait handles its own or uses insightface library
        # We might need 'insightface' package installed.
        
    except Exception as e:
        print(f"Error downloading weights: {e}")

if __name__ == "__main__":
    # Install dependency first if missing? usually better to do via pip
    download_weights()
