import pipecat
import pkgutil
import sys

print("Searching pipecat...")
stack = [pipecat]
found = []

while stack:
    pkg = stack.pop()
    if hasattr(pkg, "__path__"):
        for _, name, ispkg in pkgutil.iter_modules(pkg.__path__):
            full_name = pkg.__name__ + "." + name
            # print(full_name)
            try:
                mod = __import__(full_name, fromlist=["*"])
                if hasattr(mod, "LLMService"):
                    print(f"FOUND LLMService in {full_name}")
                if hasattr(mod, "TTSService"):
                    print(f"FOUND TTSService in {full_name}")
                if ispkg:
                    stack.append(mod)
            except Exception as e:
                # print(f"Skip {full_name}: {e}")
                pass
