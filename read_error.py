
try:
    with open("error.log", "r") as f:
        content = f.read()
    with open("trace.txt", "w") as f:
        f.write(content)
    print("Copied error.log to trace.txt")
except Exception as e:
    print(e)
