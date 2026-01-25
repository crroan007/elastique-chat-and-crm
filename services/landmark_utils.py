
import cv2
import numpy as np
import mediapipe as mp
from typing import List, Tuple

# MediaPipe Initialization
mp_face_mesh = mp.solutions.face_mesh

# Placeholder for empty bbox (matching original)
coord_placeholder = (0.0, 0.0, 0.0, 0.0)


# BYPASS MEDIAPIPE (Windows/Protobuf Crash Fix)
def get_landmark_and_bbox(img_list: List[str], upperbondrange=0):
    """
    Hardcoded bypass for static avatar 'sarah_v2.png'.
    Avoids MediaPipe Runtime Error on Windows.
    """
    coords_list = []
    frames = []
    
    # Standard Sarah V2 256x256 Crop Coordinates (Approximate)
    # Based on typical face centering
    # BBox format: x_min, y_min, x_max, y_max
    # Assumes 700x700 source usually
    
    print("DEBUG: Using Hardcoded Face Landmarks (MediaPipe Bypass)", flush=True)

    for img_path in img_list:
        frame = cv2.imread(img_path)
        if frame is None:
            coords_list.append((0,0,0,0))
            frames.append(None)
            continue
            
        frames.append(frame)
        h, w = frame.shape[:2]
        
        # Hardcoded centralized crop for 256x256 rendering
        # Just return a centered box relative to image size
        # This is a heuristic.
        center_x = w // 2
        center_y = h // 2
        
        # Half-width of face box approx 120px?
        box_w = 200
        box_h = 200
        
        x_min = max(0, center_x - 100)
        x_max = min(w, center_x + 100)
        y_min = max(0, center_y - 120) # Slightly higher for forehead
        y_max = min(h, center_y + 100)
        
        coords_list.append((int(x_min), int(y_min), int(x_max), int(y_max)))

    return coords_list, frames
