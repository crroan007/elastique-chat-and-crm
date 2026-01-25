
import os
import requests

url = "https://download.pytorch.org/models/resnet18-5c106cde.pth"
target_dir = "external/MuseTalk/models/face-parse-bisent"
target_path = os.path.join(target_dir, "resnet18-5c106cde.pth")

if not os.path.exists(target_dir):
    os.makedirs(target_dir)

print(f"Downloading {url} to {target_path}...")

try:
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(target_path, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print("Download successful.")
    else:
        print(f"Download failed: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")
