"""
Quick test script to verify automatic token refresh and caption generation setup
Run this after starting your server to verify everything is configured correctly.
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_token_status():
    """Test token status endpoint"""
    print("\n🔍 Testing Token Status...")
    try:
        response = requests.get(f"{BASE_URL}/token-status")
        data = response.json()
        print(f"   Status: {json.dumps(data, indent=2)}")
        if data.get("valid"):
            print("   ✅ Token is valid!")
        else:
            print("   ⚠️  Token is invalid or expired")
        return data.get("valid", False)
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_config():
    """Test configuration status"""
    print("\n🔍 Testing Configuration...")
    try:
        response = requests.get(f"{BASE_URL}/config-check")
        data = response.json()
        config = data.get("configuration", {})
        
        print("\n   Configuration Status:")
        print(f"   - Instagram Account: {'✅' if config.get('instagram_account_configured') else '❌'}")
        print(f"   - Access Token: {'✅' if config.get('access_token_configured') else '❌'}")
        print(f"   - FB App Credentials: {'✅' if config.get('fb_app_credentials_configured') else '❌'}")
        print(f"   - Gemini AI (Captions): {'✅' if config.get('gemini_configured') else '❌'}")
        print(f"   - Image Hosting: {'✅' if config.get('hosting_available') else '❌'}")
        
        issues = data.get("issues", [])
        if issues:
            print(f"\n   ⚠️  Issues found: {', '.join(issues)}")
        else:
            print("\n   ✅ All configurations look good!")
        
        return len(issues) == 0
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_token_refresh():
    """Test manual token refresh"""
    print("\n🔍 Testing Token Refresh...")
    try:
        response = requests.get(f"{BASE_URL}/refresh-token")
        data = response.json()
        
        if data.get("success"):
            print("   ✅ Token refresh successful!")
            if data.get("saved_to_env"):
                print("   ✅ Token saved to .env automatically!")
            else:
                print("   ⚠️  Token refreshed but not saved to .env (check permissions)")
            print(f"   New token expires in: {data.get('expires_in', 'N/A')} seconds")
        else:
            print(f"   ⚠️  Refresh failed: {data.get('message', 'Unknown error')}")
        
        return data.get("success", False)
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_caption_generation():
    """Test caption generation"""
    print("\n🔍 Testing Caption Generation...")
    try:
        response = requests.post(
            f"{BASE_URL}/generate-caption",
            data={
                "prompt": "A beautiful sunset over mountains",
                "keywords": "sunset,mountains,nature",
                "tone": "inspiring",
                "hashtag_count": "8"
            }
        )
        data = response.json()
        
        print("   ✅ Caption generated!")
        print(f"\n   Caption: {data.get('caption', 'N/A')}")
        print(f"   Hashtags: {', '.join(data.get('hashtags', []))}")
        print(f"\n   Full Caption:\n   {data.get('full_caption', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print("   Make sure GEMINI_API_KEY is set in .env")
        return False

def main():
    print("=" * 60)
    print("🚀 Automation Setup Verification")
    print("=" * 60)
    print("\nMake sure your server is running: python main.py")
    print("Press Enter to continue...")
    input()
    
    results = {
        "config": test_config(),
        "token_status": test_token_status(),
        "caption_gen": test_caption_generation(),
    }
    
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)
    
    if all(results.values()):
        print("\n✅ Everything is working perfectly!")
        print("\nYou can now:")
        print("  1. Post with auto captions using: auto_caption=true + prompt")
        print("  2. Token will refresh automatically on startup and before posts")
    else:
        print("\n⚠️  Some checks failed. Review the output above.")
        if not results["config"]:
            print("  - Fix configuration issues in .env")
        if not results["token_status"]:
            print("  - Check token status or refresh manually")
        if not results["caption_gen"]:
            print("  - Verify GEMINI_API_KEY is set correctly")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
