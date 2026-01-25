
import requests
import os

url = "https://huggingface.co/ManyOtherFunctions/face-parse-bisent/resolve/main/79999_iter.pth"
target_dir = os.path.abspath("external/MuseTalk/models/face-parse-bisent")
target_file = os.path.join(target_dir, "79999_iter.pth")

if not os.path.exists(target_dir):
    os.makedirs(target_dir)

print(f"Downloading {url} to {target_file}")

try:
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(target_file, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print("Download Complete.")
except Exception as e:
    print(f"Download Failed: {e}")
