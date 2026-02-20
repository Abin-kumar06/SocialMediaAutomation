import requests

BASE_URL = "http://localhost:8000"

def test_url_post():
    print("Testing /upload-post with URL...")
    image_url = "https://picsum.photos/1080/1080"
    
    # Form data
    data = {
        'image_url': image_url,
        'caption': 'Testing URL post from antigravity'
    }
    
    try:
        response = requests.post(f"{BASE_URL}/upload-post", data=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_url_post()
