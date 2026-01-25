
try:
    with open("error.log", "rb") as f:
        data = f.read()
    try:
        content = data.decode('utf-16')
    except:
        content = data.decode('utf-8', errors='replace')
        
    print(content)
except Exception as e:
    print(f"Error reading error.log: {e}")
