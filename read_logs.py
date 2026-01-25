import re

def parse_logs():
    print("--- Reading Server Log ---")
    try:
        with open("server.log", "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        found = False
        for line in lines[-200:]: # Check last 200 lines
            if "Analyst" in line:
                print(line.strip())
                found = True
        
        if not found:
            print("No 'Analyst' logs found in the last 200 lines.")
            
    except Exception as e:
        print(f"Error reading log: {e}")

if __name__ == "__main__":
    parse_logs()
