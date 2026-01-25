import pipecat
import pipecat.services
import os
print(f"Path: {pipecat.services.__file__}")
print("Contents:", os.listdir(os.path.dirname(pipecat.services.__file__)))
