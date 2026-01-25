
import os
import cv2
import traceback
from services.landmark_utils import get_landmark_and_bbox

def test_landmark():
    try:
        image_path = "static/img/sarah_avatar.jpg"
        if not os.path.exists(image_path):
            print(f"Image not found: {image_path}")
            return
            
        print(f"Processing {image_path}...")
        coords, frames = get_landmark_and_bbox([image_path], bbox_shift=0)
        
        print(f"Success!")
        print(f"Coords: {coords}")
        print(f"Frames: {len(frames)}")
        
        if len(coords) > 0:
            print(f"First Coord: {coords[0]}")
            
    except Exception as e:
        print(f"Landmark Test Failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_landmark()
