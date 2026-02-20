import requests
import json

API_URL = "http://localhost:8000"

def test_generate_caption(platform, topic):
    print(f"Testing caption generation for {platform}...")
    data = {
        "prompt": topic,
        "platform": platform
    }
    try:
        response = requests.post(f"{API_URL}/generate-caption", data=data, timeout=70)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Caption: {result.get('caption')}")
            print(f"Hashtags: {result.get('hashtags')}")
            print(f"Full Caption:\n{result.get('full_caption')}\n")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    platforms = ["instagram", "linkedin", "x"]
    topic = "The benefits of local AI with Ollama and llama3"
    
    for p in platforms:
        test_generate_caption(p, topic)
