
try:
    print("Importing WhisperModel...")
    from transformers import WhisperModel
    print("Success:", WhisperModel)
except Exception as e:
    print("Failed:", e)
