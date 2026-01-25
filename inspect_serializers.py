import pipecat.serializers
import os
print(f"Path: {pipecat.serializers.__file__}")
print("Contents:", os.listdir(os.path.dirname(pipecat.serializers.__file__)))
