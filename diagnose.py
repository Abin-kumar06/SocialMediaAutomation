"""
Instagram API Diagnostic Tool
Tests your credentials and helps identify issues
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Load credentials
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v24.0")
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

print("=" * 70)
print("Instagram API Diagnostic Tool")
print("=" * 70)
print()

# Check 1: Credentials configured
print("✓ Step 1: Checking credentials...")
if not INSTAGRAM_ACCOUNT_ID:
    print("❌ INSTAGRAM_ACCOUNT_ID not set in .env file!")
    exit(1)
if not PAGE_ACCESS_TOKEN:
    print("❌ PAGE_ACCESS_TOKEN not set in .env file!")
    exit(1)

print(f"✅ Instagram Account ID: {INSTAGRAM_ACCOUNT_ID}")
print(f"✅ Access Token: {PAGE_ACCESS_TOKEN[:20]}...{PAGE_ACCESS_TOKEN[-10:]}")
print()

# Check 2: Test access token validity
print("✓ Step 2: Testing access token...")
debug_url = f"{GRAPH_API_BASE}/debug_token"
debug_params = {
    'input_token': PAGE_ACCESS_TOKEN,
    'access_token': PAGE_ACCESS_TOKEN
}

try:
    response = requests.get(debug_url, params=debug_params, timeout=10)
    result = response.json()
    
    if 'data' in result:
        token_data = result['data']
        is_valid = token_data.get('is_valid', False)
        
        if is_valid:
            print(f"✅ Access token is VALID")
            print(f"   App ID: {token_data.get('app_id', 'N/A')}")
            print(f"   User ID: {token_data.get('user_id', 'N/A')}")
            print(f"   Expires: {token_data.get('expires_at', 'Never')}")
            
            # Check scopes
            scopes = token_data.get('scopes', [])
            print(f"   Permissions: {', '.join(scopes)}")
            
            required_scopes = ['instagram_basic', 'instagram_content_publish']
            missing_scopes = [s for s in required_scopes if s not in scopes]
            
            if missing_scopes:
                print(f"⚠️  Missing permissions: {', '.join(missing_scopes)}")
                print(f"   You need to request these permissions in Graph API Explorer")
        else:
            print(f"❌ Access token is INVALID or EXPIRED")
            print(f"   Error: {token_data.get('error', {}).get('message', 'Unknown error')}")
            exit(1)
    else:
        print(f"❌ Could not validate token")
        print(f"   Response: {result}")
        exit(1)
except Exception as e:
    print(f"❌ Error checking token: {e}")
    exit(1)

print()

# Check 3: Get Instagram account info
print("✓ Step 3: Fetching Instagram account info...")
account_url = f"{GRAPH_API_BASE}/{INSTAGRAM_ACCOUNT_ID}"
account_params = {
    'fields': 'id,username,name,biography,followers_count,follows_count,media_count',
    'access_token': PAGE_ACCESS_TOKEN
}

try:
    response = requests.get(account_url, params=account_params, timeout=10)
    result = response.json()
    
    if 'error' in result:
        print(f"❌ Error fetching account info:")
        print(f"   Message: {result['error']['message']}")
        print(f"   Code: {result['error'].get('code', 'N/A')}")
        print(f"   Subcode: {result['error'].get('error_subcode', 'N/A')}")
        print()
        print("Possible issues:")
        print("   1. Instagram Account ID is incorrect")
        print("   2. Access token doesn't have permission for this account")
        print("   3. Account is not a Business or Creator account")
        exit(1)
    else:
        print(f"✅ Account found!")
        print(f"   ID: {result.get('id', 'N/A')}")
        print(f"   Username: @{result.get('username', 'N/A')}")
        print(f"   Name: {result.get('name', 'N/A')}")
        print(f"   Followers: {result.get('followers_count', 'N/A')}")
        print(f"   Following: {result.get('follows_count', 'N/A')}")
        print(f"   Posts: {result.get('media_count', 'N/A')}")
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

print()

# Check 4: Test creating a media container with a test image
print("✓ Step 4: Testing media container creation (DRY RUN)...")
print("   Using Instagram's test image URL...")

test_image_url = "https://www.instagram.com/static/images/ico/favicon-192.png/68d99ba29cc8.png"
test_caption = "Test post - Instagram API diagnostic"

container_url = f"{GRAPH_API_BASE}/{INSTAGRAM_ACCOUNT_ID}/media"
container_payload = {
    'image_url': test_image_url,
    'caption': test_caption,
    'access_token': PAGE_ACCESS_TOKEN
}

try:
    response = requests.post(container_url, data=container_payload, timeout=30)
    result = response.json()
    
    if 'error' in result:
        error = result['error']
        print(f"❌ Cannot create media container:")
        print(f"   Message: {error.get('message', 'Unknown error')}")
        print(f"   Code: {error.get('code', 'N/A')}")
        print(f"   Subcode: {error.get('error_subcode', 'N/A')}")
        print(f"   Type: {error.get('type', 'N/A')}")
        print()
        
        # Common issues
        error_msg = error.get('message', '').lower()
        if 'permissions' in error_msg or 'scope' in error_msg:
            print("❓ Likely issue: Missing permissions")
            print("   Solution: Go to Graph API Explorer and request:")
            print("   - instagram_basic")
            print("   - instagram_content_publish")
            print("   - pages_read_engagement")
            print()
        elif 'business account' in error_msg:
            print("❓ Likely issue: Account is not a Business/Creator account")
            print("   Solution: Convert your Instagram to Business account in the app")
            print()
        elif 'image' in error_msg:
            print("❓ Likely issue: Image URL problem")
            print("   This is expected for dry run - your actual images should work")
            print()
        else:
            print("❓ Check the error message above for more details")
            print()
        
        print("Documentation:")
        print("   https://developers.facebook.com/docs/instagram-api/guides/content-publishing")
        exit(1)
    else:
        creation_id = result.get('id')
        print(f"✅ Media container created successfully!")
        print(f"   Creation ID: {creation_id}")
        print()
        print(f"🎉 All checks passed! Your API should work correctly.")
        print()
        print(f"Note: The test container was NOT published to Instagram.")
        print(f"      It will expire in 24 hours if not published.")
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

print()
print("=" * 70)
print("Diagnostic Complete!")
print("=" * 70)