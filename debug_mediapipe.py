
import mediapipe as mp
print(f"MediaPipe Version: {mp.__version__}")
print(f"Dir(mp): {dir(mp)}")
try:
    from mediapipe.python.solutions import face_mesh
    print("Direct Import: Success")
except Exception as e:
    print(f"Direct Import Failed: {e}")
