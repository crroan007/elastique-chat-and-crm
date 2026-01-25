import requests

BASE_URL = "http://localhost:8000"

def trigger_error():
    url = f"{BASE_URL}/chat"
    # Use the trigger phrase
    data = {"message": "ive been dealing with headaches and joint pain recenlty", "user_name": "TestUser", "user_email": "test@test.com"}
    print(f"Sending request to {url}...")
    try:
        r = requests.post(url, data=data)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    trigger_error()
