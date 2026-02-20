# Quick Start: Auto Captions & Token Refresh

## ✅ You're Already Set Up!

Your `.env` file already has everything configured:
- ✅ `FB_APP_ID` and `FB_APP_SECRET` → Auto token refresh enabled
- ✅ `GEMINI_API_KEY` → Auto caption generation enabled

---

## 🚀 Steps to Use

### Step 1: Start Your Server

```bash
python main.py
```

**What happens:**
- Server starts
- Token is automatically checked and refreshed if needed
- New token is saved to `.env` automatically
- You'll see: `✓ Token refreshed and saved to .env` (if refresh happened)

### Step 2: Post with Auto Captions

**Option A: Using cURL**

```bash
curl -X POST "http://localhost:8000/upload-post" \
  -F "file=@your_image.jpg" \
  -F "auto_caption=true" \
  -F "prompt=Describe your image here" \
  -F "keywords=keyword1,keyword2" \
  -F "tone=professional" \
  -F "hashtag_count=10"
```

**Option B: Using Python**

```python
import requests

response = requests.post(
    "http://localhost:8000/upload-post",
    files={"file": open("your_image.jpg", "rb")},
    data={
        "auto_caption": "true",
        "prompt": "A beautiful sunset over mountains",
        "keywords": "sunset,mountains,nature",
        "tone": "inspiring",
        "hashtag_count": "10"
    }
)
print(response.json())
```

**Option C: Using image URL**

```bash
curl -X POST "http://localhost:8000/upload-post" \
  -F "image_url=https://example.com/image.jpg" \
  -F "auto_caption=true" \
  -F "prompt=Modern workspace setup"
```

### Step 3: That's It!

- ✅ Caption is generated automatically
- ✅ Hashtags are added automatically  
- ✅ Token is refreshed automatically before posting
- ✅ Post goes live on Instagram

---

## 🔍 Verify Everything Works

Run the test script:

```bash
python test_automation.py
```

This will check:
- ✅ Configuration status
- ✅ Token validity
- ✅ Caption generation
- ✅ Token refresh capability

---

## 📋 API Endpoints Reference

### Post with Auto Caption
```
POST /upload-post
- auto_caption: true (required)
- prompt: "Describe your image" (required)
- keywords: "word1,word2" (optional)
- tone: "professional" (optional)
- hashtag_count: 8 (optional, default: 8)
```

### Check Token Status
```
GET /token-status
```

### Manually Refresh Token
```
GET /refresh-token
```

### Check Configuration
```
GET /config-check
```

### Generate Caption Only (without posting)
```
POST /generate-caption
- prompt: "Describe your image"
- keywords: "word1,word2" (optional)
- tone: "professional" (optional)
- hashtag_count: 8 (optional)
```

---

## 🎯 What Happens Automatically

### Token Refresh
1. **On Startup:** Checks token → Refreshes if needed → Saves to `.env`
2. **Before Each Post:** Checks token → Refreshes if needed → Saves to `.env` → Posts

### Caption Generation
1. You provide `prompt` describing the image
2. AI generates caption + hashtags
3. Post is created with generated content

---

## ⚠️ Troubleshooting

### Token Refresh Not Working?

1. **Check credentials:**
   ```bash
   curl http://localhost:8000/config-check
   ```
   Look for `"fb_app_credentials_configured": true`

2. **Check token status:**
   ```bash
   curl http://localhost:8000/token-status
   ```

3. **Manually refresh:**
   ```bash
   curl http://localhost:8000/refresh-token
   ```

### Caption Generation Not Working?

1. **Check Gemini API key:**
   ```bash
   curl http://localhost:8000/config-check
   ```
   Look for `"gemini_configured": true`

2. **Test caption generation:**
   ```bash
   curl -X POST "http://localhost:8000/generate-caption" \
     -F "prompt=Test caption"
   ```

---

## 📚 More Details

- **Full automation guide:** See `AUTOMATION_GUIDE.md`
- **LinkedIn setup:** See `LINKEDIN_SETUP.md`
- **API documentation:** Visit `http://localhost:8000/docs` when server is running

---

## ✨ Summary

**You're ready to go!** Just:
1. Start server: `python main.py`
2. Post with: `auto_caption=true` + `prompt="your description"`
3. Everything else happens automatically! 🎉
