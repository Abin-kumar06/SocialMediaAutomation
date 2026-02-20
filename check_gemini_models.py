"""
Check which Gemini models are available for your API key
"""
import requests
import os
import json
from dotenv import load_dotenv
from pathlib import Path

# Load .env
_PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(_PROJECT_ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY not found in .env file")
    exit(1)

print("=" * 60)
print("🔍 Checking Available Gemini Models")
print("=" * 60)
print(f"\nAPI Key: {GEMINI_API_KEY[:20]}...{GEMINI_API_KEY[-10:]}\n")

# First, try to list all available models
print("Step 1: Listing all available models from API...\n")
list_url = f"https://generativelanguage.googleapis.com/v1/models?key={GEMINI_API_KEY}"

try:
    list_response = requests.get(list_url, timeout=10)
    if list_response.status_code == 200:
        models_data = list_response.json()
        if "models" in models_data:
            print(f"✅ Found {len(models_data['models'])} available models:\n")
            available_from_list = []
            for model in models_data["models"]:
                model_name = model.get("name", "").replace("models/", "")
                if model_name:
                    available_from_list.append(model_name)
                    print(f"   - {model_name}")
            
            print(f"\n✅ These models are available for your API key!")
            print(f"\n💡 Recommended: Use one of the models above")
            if available_from_list:
                # Prefer flash models for speed/cost
                recommended = None
                for model in available_from_list:
                    if "flash" in model.lower():
                        recommended = model
                        break
                if not recommended:
                    recommended = available_from_list[0]
                
                print(f"\n💡 Recommended model: {recommended}")
                print(f"\n   Update your .env file:")
                print(f"   AI_MODEL={recommended}")
            exit(0)
        else:
            print("⚠️  API returned 200 but no models list found")
    elif list_response.status_code == 403:
        print("❌ Access denied (403) - API key may not have proper permissions")
        print("\n   Possible fixes:")
        print("   1. Go to: https://aistudio.google.com/app/apikey")
        print("   2. Create a new API key")
        print("   3. Or enable 'Generative Language API' in Google Cloud Console")
        print(f"\n   Error details: {list_response.text[:200]}")
    elif list_response.status_code == 404:
        print("❌ Endpoint not found (404) - API key may be invalid")
    else:
        print(f"⚠️  Status {list_response.status_code}: {list_response.text[:200]}")
except Exception as e:
    print(f"❌ Error listing models: {e}\n")

# Fallback: Test individual models
print("\nStep 2: Testing individual models...\n")

MODELS_TO_TEST = [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro-latest",
    "gemini-pro",
    "gemini-pro-vision",
    "gemini-1.0-pro",
    "gemini-1.0-pro-vision",
]

available_models = []
unavailable_models = []

for model in MODELS_TO_TEST:
    url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={GEMINI_API_KEY}"
    
    # Try a simple test request
    payload = {
        "contents": [{
            "parts": [{
                "text": "Say 'test'"
            }]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            available_models.append(model)
            print(f"✅ {model:30s} - Available")
        elif response.status_code == 404:
            unavailable_models.append(model)
            print(f"❌ {model:30s} - Not found (404)")
        elif response.status_code == 403:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            error_msg = error_data.get('error', {}).get('message', 'Access denied')
            print(f"⚠️  {model:30s} - Access denied (403): {error_msg[:50]}")
            unavailable_models.append(model)
        elif response.status_code == 400:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            error_msg = error_data.get('error', {}).get('message', 'Bad request')
            print(f"⚠️  {model:30s} - Bad request (400): {error_msg[:50]}")
            unavailable_models.append(model)
        else:
            print(f"⚠️  {model:30s} - Status {response.status_code}")
            unavailable_models.append(model)
    except Exception as e:
        print(f"❌ {model:30s} - Error: {str(e)[:50]}")
        unavailable_models.append(model)

print("\n" + "=" * 60)
print("📊 Summary")
print("=" * 60)

if available_models:
    print(f"\n✅ Available Models ({len(available_models)}):")
    for model in available_models:
        print(f"   - {model}")
    
    # Recommend the best model
    recommended = None
    if "gemini-1.5-flash" in available_models:
        recommended = "gemini-1.5-flash"
    elif "gemini-1.5-pro" in available_models:
        recommended = "gemini-1.5-pro"
    elif "gemini-1.5-flash-latest" in available_models:
        recommended = "gemini-1.5-flash-latest"
    elif available_models:
        recommended = available_models[0]
    
    if recommended:
        print(f"\n💡 Recommended model: {recommended}")
        print(f"\n   Update your .env file:")
        print(f"   AI_MODEL={recommended}")
else:
    print("\n❌ No available models found!")
    print("\nPossible issues:")
    print("  1. API key is invalid or expired")
    print("  2. API key doesn't have access to Gemini models")
    print("  3. Check your Google Cloud project settings")
    print("  4. Verify the API key at: https://aistudio.google.com/app/apikey")

print("\n" + "=" * 60)
