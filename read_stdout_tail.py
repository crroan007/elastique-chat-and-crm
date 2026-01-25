
try:
    with open("run_output_v2_attempt2.txt", "rb") as f:
        data = f.read()
    try:
        content = data.decode('utf-16')
    except:
        content = data.decode('utf-8', errors='replace')
        
    print("--- LAST 4000 CHARS ---")
    print(content[-4000:])
        
except Exception as e:
    print(f"Error reading log: {e}")
