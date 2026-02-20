import requests
import sys

BASE_URL = "http://localhost:8000"

def test_token_status():
    print("Testing /token-status...")
    try:
        response = requests.get(f"{BASE_URL}/token-status")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

def test_refresh_token():
    print("\nTesting /refresh-token...")
    try:
        response = requests.get(f"{BASE_URL}/refresh-token")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

def test_url_post():
    print("\nTesting /upload-post with URL...")
    # Using a sample public image URL
    image_url = "https://raw.githubusercontent.com/python-pillow/Pillow/master/docs/conf.py" # Not an image, wait
    image_url = "https://picsum.photos/1080/1080" # Better
    
    payload = {
        'image_url': image_url,
        'caption': 'Test post from URL'
    }
    
    try:
        response = requests.post(f"{BASE_URL}/upload-post", data=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_token_status()
    test_refresh_token()
    # test_url_post() # Uncomment to test actual posting if server is running
