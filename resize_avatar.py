
from PIL import Image
import os

path = "static/evan_avatar.jpg"
if os.path.exists(path):
    img = Image.open(path)
    print(f"Original Size: {img.size}")
    
    # Resize to 512x512 (SadTalker optimal)
    img = img.resize((512, 512), Image.Resampling.LANCZOS)
    img.save(path)
    print(f"Resized to 512x512: {path}")
else:
    print("Image not found")
