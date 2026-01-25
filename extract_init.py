import re
with open("real_transport_source.py", "r", encoding="utf-16le") as f:
    content = f.read()

match = re.search(r"async def _receive_messages.*?def ", content, re.DOTALL)
if match:
    with open("receive_logic.txt", "w", encoding="utf-8") as out:
        out.write(match.group(0))
else:
     # If it's the last method, it might not look like "def "... try to capture till end
     match = re.search(r"async def _receive_messages.*", content, re.DOTALL)
     if match:
        with open("receive_logic.txt", "w", encoding="utf-8") as out:
            out.write(match.group(0))
     else:
        with open("receive_logic.txt", "w", encoding="utf-8") as out:
            out.write("Not found.")



