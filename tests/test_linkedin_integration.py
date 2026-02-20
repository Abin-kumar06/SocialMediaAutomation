import requests
import json

API_URL = "http://localhost:8000"

def test_linkedin_caption():
    print("--- Testing LinkedIn Caption Generation ---")
    data = {
        "prompt": "Connecting businesses with local AI automation solutions",
        "platform": "linkedin"
    }
    try:
        response = requests.post(f"{API_URL}/generate-caption", data=data, timeout=70)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Full Caption:\n{result.get('full_caption')}\n")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Connection Error: {e}")

def test_linkedin_connect_url():
    print("--- Testing LinkedIn Connect URL ---")
    try:
        response = requests.get(f"{API_URL}/api/platforms/linkedin/connect", allow_redirects=False)
        print(f"Status: {response.status_code}")
        if response.status_code == 307:
            print(f"Auth URL: {response.headers.get('Location')}\n")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    test_linkedin_caption()
    test_linkedin_connect_url()
