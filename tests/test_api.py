"""
Test script for Instagram Auto Post API
"""
import requests
import json

API_URL = "http://localhost:8000"


def test_health():
    """Test health check"""
    print("Testing health check...")
    response = requests.get(f"{API_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")


def test_config():
    """Test configuration check"""
    print("Testing config check...")
    response = requests.get(f"{API_URL}/config-check")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")


def test_upload(image_path: str, caption: str):
    """Test image upload and post"""
    print(f"Testing upload...")
    print(f"Image: {image_path}")
    print(f"Caption: {caption}\n")
    
    try:
        with open(image_path, 'rb') as img:
            files = {'file': img}
            data = {'caption': caption}
            
            response = requests.post(
                f"{API_URL}/upload-post",
                files=files,
                data=data
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}\n")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('instagram_post_url'):
                    print(f"✅ Success! View at: {result['instagram_post_url']}")
            else:
                print(f"❌ Failed!")
                
    except FileNotFoundError:
        print(f"❌ File not found: {image_path}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Instagram Auto Post API - Test Suite")
    print("=" * 60)
    print()
    
    test_health()
    test_config()
    
    # Uncomment to test upload
    # test_upload("test_image.jpg", "Test post! 🚀")