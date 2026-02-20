# Automation Guide: Auto Captions & Token Refresh

This guide explains how to use **automatic caption generation** and how **automatic token refresh** works.

---

## ✅ Automatic Caption Generation

### What You Need

Your `.env` already has:
- ✅ `GEMINI_API_KEY` - Configured ✓
- ✅ `AI_MODEL` - Set to `gemini-pro-vision` ✓

### How to Use Auto Captions

When posting to Instagram, set `auto_caption=true` and provide a `prompt` describing your image.

**Example API Request:**

```bash
# Using cURL
curl -X POST "http://localhost:8000/upload-post" \
  -F "file=@your_image.jpg" \
  -F "auto_caption=true" \
  -F "prompt=A beautiful sunset over mountains with vibrant colors" \
  -F "keywords=sunset,mountains,nature,photography" \
  -F "tone=inspiring" \
  -F "hashtag_count=10"
```

**Parameters:**
- `auto_caption=true` - **Required** to enable auto-generation
- `prompt` - **Required** - Describe what's in the image (e.g., "A coffee cup on a wooden table")
- `keywords` - **Optional** - Comma-separated keywords (e.g., "coffee,wooden,minimalist")
- `tone` - **Optional** - Caption tone (e.g., "playful", "professional", "inspiring", "casual")
- `hashtag_count` - **Optional** - Number of hashtags (default: 8, max: 20)

**Example with image URL:**

```bash
curl -X POST "http://localhost:8000/upload-post" \
  -F "image_url=https://example.com/image.jpg" \
  -F "auto_caption=true" \
  -F "prompt=Modern workspace setup with laptop and plants" \
  -F "keywords=workspace,productivity,plants" \
  -F "tone=professional"
```

**What Happens:**
1. The AI (Gemini) generates a caption based on your prompt
2. Relevant hashtags are added automatically
3. The caption + hashtags are posted to Instagram

---

## 🔄 Automatic Token Refresh

### Current Status

✅ **You're already set up!** Your `.env` has:
- ✅ `FB_APP_ID=2474313239649853`
- ✅ `FB_APP_SECRET=9aaeb8fbe465a034d1502f07d09aec34`
- ✅ `PAGE_ACCESS_TOKEN=...` (your current token)

### How It Works

**Automatic refresh happens in 2 places:**

1. **On App Startup** 🚀
   - When you start the server, it checks if the token is valid
   - If expired/invalid, it automatically refreshes and saves to `.env`
   - You'll see: `✓ Token refreshed and saved to .env` in the console

2. **Before Each Post** 📸
   - Every time you post, it checks the token first
   - If expired, it refreshes automatically and saves to `.env`
   - Then proceeds with the post

### What You Need to Do

**Nothing!** The automation is already active. Just:

1. **Start your server:**
   ```bash
   python main.py
   # or
   uvicorn main:app --reload
   ```

2. **Check token status anytime:**
   ```bash
   curl http://localhost:8000/token-status
   ```

3. **Manually refresh if needed:**
   ```bash
   curl http://localhost:8000/refresh-token
   ```
   Response will show: `"saved_to_env": true` if it was saved successfully.

### How Token Refresh Works

1. **Facebook Token Exchange:**
   - Uses your `FB_APP_ID` and `FB_APP_SECRET`
   - Exchanges your current `PAGE_ACCESS_TOKEN` for a new long-lived token
   - New token is valid for ~60 days

2. **Auto-Save to .env:**
   - New token is automatically written to `.env`
   - Your `PAGE_ACCESS_TOKEN` line is updated
   - Next time you restart, it uses the fresh token

3. **In-Memory Update:**
   - Current running app uses the new token immediately
   - No restart needed for the current session

### Troubleshooting

**If token refresh fails:**

1. **Check your credentials:**
   ```bash
   curl http://localhost:8000/config-check
   ```
   Look for `"fb_app_credentials_configured": true`

2. **Verify token status:**
   ```bash
   curl http://localhost:8000/token-status
   ```

3. **Common issues:**
   - ❌ Token expired beyond refresh window → Get a new token from Facebook Graph API Explorer
   - ❌ `FB_APP_ID` or `FB_APP_SECRET` incorrect → Update in `.env`
   - ❌ App permissions changed → Re-authorize your app

**Manual token refresh:**
If automatic refresh fails, you can manually get a new token:
1. Go to [Facebook Graph API Explorer](https://developers.facebook.com/tools/explorer/)
2. Select your app
3. Generate a new Page Access Token with `instagram_basic`, `instagram_content_publish`, `pages_show_list` permissions
4. Copy the token and update `PAGE_ACCESS_TOKEN` in `.env`

---

## 📋 Quick Reference

### Post with Auto Caption

```bash
POST /upload-post
- file: (image file)
- auto_caption: true
- prompt: "Describe your image"
- keywords: "keyword1,keyword2" (optional)
- tone: "professional" (optional)
- hashtag_count: 10 (optional)
```

### Check Token Status

```bash
GET /token-status
```

### Manually Refresh Token

```bash
GET /refresh-token
```

### Check Configuration

```bash
GET /config-check
```

---

## 🎯 Summary

**Auto Captions:**
- ✅ Already configured (GEMINI_API_KEY is set)
- ✅ Use `auto_caption=true` + `prompt` when posting
- ✅ AI generates caption + hashtags automatically

**Auto Token Refresh:**
- ✅ Already configured (FB_APP_ID + FB_APP_SECRET are set)
- ✅ Happens automatically on startup and before posts
- ✅ New tokens are saved to `.env` automatically
- ✅ No manual steps needed!

**You're all set!** Just start posting with `auto_caption=true` and the system handles everything automatically. 🚀
