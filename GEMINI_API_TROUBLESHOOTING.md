# Gemini API Troubleshooting Guide

## Problem: All Models Return 404

If you're getting 404 errors for all Gemini models, here's how to fix it:

---

## Solution 1: Get a New API Key from Google AI Studio

**This is the easiest solution:**

1. **Go to Google AI Studio:**
   - Visit: https://aistudio.google.com/app/apikey
   - Sign in with your Google account

2. **Create a new API key:**
   - Click **"Create API Key"**
   - Select your Google Cloud project (or create a new one)
   - Copy the API key

3. **Update your `.env` file:**
   ```env
   GEMINI_API_KEY=your_new_api_key_here
   AI_MODEL=gemini-1.5-flash
   ```

4. **Test again:**
   ```bash
   python check_gemini_models.py
   ```

---

## Solution 2: Enable Generative Language API in Google Cloud

If you're using an existing Google Cloud project:

1. **Go to Google Cloud Console:**
   - Visit: https://console.cloud.google.com/

2. **Enable the API:**
   - Navigate to **APIs & Services** → **Library**
   - Search for **"Generative Language API"**
   - Click **Enable**

3. **Verify API key:**
   - Go to **APIs & Services** → **Credentials**
   - Find your API key
   - Make sure it has access to **Generative Language API**

---

## Solution 3: Check API Key Restrictions

If your API key has restrictions:

1. **Go to Google Cloud Console:**
   - Visit: https://console.cloud.google.com/apis/credentials

2. **Edit your API key:**
   - Click on your API key
   - Under **API restrictions**, make sure:
     - Either **"Don't restrict key"** is selected, OR
     - **"Restrict key"** includes **"Generative Language API"**

3. **Save and test again**

---

## Solution 4: Use Alternative AI Service

If Gemini API continues to have issues, you can switch to other AI services:

### Option A: OpenAI (if you have access)
```env
# You'd need to modify the code to use OpenAI instead
OPENAI_API_KEY=your_openai_key
```

### Option B: Use Manual Captions
Simply don't use `auto_caption=true` and provide your own captions:
```bash
curl -X POST "http://localhost:8000/upload-post" \
  -F "file=@image.jpg" \
  -F "caption=Your custom caption here"
```

---

## Quick Test

After updating your API key, test it:

```bash
# Test which models are available
python check_gemini_models.py

# Or test via API (if server is running)
curl http://localhost:8000/check-gemini-models
```

---

## Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| 404 Not Found | API key invalid or API not enabled | Get new key from AI Studio |
| 403 Forbidden | API key restricted or no permissions | Enable Generative Language API |
| 401 Unauthorized | API key expired or invalid | Create new API key |
| All models 404 | Wrong API endpoint or key format | Use key from https://aistudio.google.com/app/apikey |

---

## Recommended Steps

1. ✅ **Get a fresh API key from Google AI Studio** (easiest)
2. ✅ **Update `.env` with the new key**
3. ✅ **Set `AI_MODEL=gemini-1.5-flash`** (most common)
4. ✅ **Run `python check_gemini_models.py`** to verify
5. ✅ **Restart your server**

---

## Need Help?

- **Google AI Studio:** https://aistudio.google.com/app/apikey
- **API Documentation:** https://ai.google.dev/docs
- **Google Cloud Console:** https://console.cloud.google.com/
