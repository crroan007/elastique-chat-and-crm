import requests
import time
import json
import datetime

url = "http://localhost:8000/chat"
payload = {
    "message": "Explain the lymphatic system in detail.", 
    "user_email": "test_script@test.com"
}

print(f"[{datetime.datetime.now()}] Sending request to {url}...")
start_time = time.time()

try:
    with requests.post(url, data=payload, stream=True) as r:
        print(f"[{datetime.datetime.now()}] Status Code: {r.status_code}")
        print(f"[{datetime.datetime.now()}] Headers: {r.headers}")
        
        first_byte_time = None
        chunk_count = 0
        
        if r.encoding is None:
            r.encoding = 'utf-8'

        for line in r.iter_lines(decode_unicode=True):
            current_time = time.time()
            if first_byte_time is None:
                first_byte_time = current_time
                latency = first_byte_time - start_time
                print(f"[{datetime.datetime.now()}] FIRST BYTE RECEIVED. Latency: {latency:.2f}s")
            
            if line:
                chunk_count += 1
                try:
                    data = json.loads(line)
                    type_ = data.get("type", "unknown")
                    content = data.get("content", "")[:20] if data.get("content") else ""
                    url_ = data.get("url", "")
                    print(f"[{datetime.datetime.now()}] Chunk {chunk_count}: Type={type_} | Content/URL={content}{url_}")
                except json.JSONDecodeError:
                    print(f"[{datetime.datetime.now()}] Chunk {chunk_count}: (Non-JSON) {line[:50]}...")

        end_time = time.time()
        print(f"[{datetime.datetime.now()}] Stream finished. Total Duration: {end_time - start_time:.2f}s")

except Exception as e:
    print(f"Error: {e}")
