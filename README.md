# 📸 Instagram Auto Post API

A powerful FastAPI application for uploading images directly and posting them to Instagram automatically. Includes smart image processing with automatic aspect ratio adjustment and cloud image hosting support.

## ✨ Features

- ✅ **Automatic Image Resizing** - Intelligently crops and resizes images to match Instagram requirements
- ✅ **Smart Aspect Ratio Detection** - Automatically identifies and adjusts to the correct format:
  - Square (1:1) - 1080×1080px
  - Portrait (4:5) - 1080×1350px
  - Landscape (1.91:1) - 1080×566px
- ✅ **Multiple Image Hosting** - Support for ImgBB and Imgur APIs
- ✅ **Dimension Validation** - Prevents upload errors by validating before posting
- ✅ **Direct Instagram Integration** - Uses Facebook Graph API for posting
- ✅ **Web UI** - Built-in HTML interface for testing uploads
- ✅ **REST API** - Full-featured API endpoints with documentation

## 📁 Project Structure

```
SM_autopost/
│
├── app/
│   ├── __init__.py          # App module initialization
│   ├── config.py            # Configuration & environment settings
│   ├── models.py            # Pydantic request/response models
│   └── services.py          # Business logic (Image & Instagram services)
│
├── static/
│   └── test_upload.html     # Web UI for testing uploads
│
├── tests/
│   └── test_api.py          # API test scripts
│
├── uploads/                 # Temporary file storage
├── main.py                  # FastAPI application entry point
├── requirements.txt         # Python dependencies
├── diagnose.py             # Diagnostic utility
├── STRUCTURE.md            # Project structure documentation
└── README.md               # This file
```

## 🚀 Quick Start

### 1. Clone & Install

```bash
cd SM_autopost
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Create .env file with your credentials
cat > .env << EOF
INSTAGRAM_ACCOUNT_ID=your_account_id
PAGE_ACCESS_TOKEN=your_page_token
IMGBB_API_KEY=your_imgbb_key
# or
IMGUR_CLIENT_ID=your_imgur_client_id
GRAPH_API_VERSION=v18.0
GRAPH_API_BASE=https://graph.instagram.com
EOF
```

Required environment variables:
- `INSTAGRAM_ACCOUNT_ID` - Your Instagram Business Account ID (from Meta Business Suite)
- `PAGE_ACCESS_TOKEN` - Facebook Page Access Token with Instagram permissions
- `IMGBB_API_KEY` or `IMGUR_CLIENT_ID` - Cloud image hosting service credentials
- `GRAPH_API_VERSION` - Facebook Graph API version (default: v18.0)
- `IMGBB_API_KEY` - ImgBB API key (get from https://api.imgbb.com/)

## 🚀 Running the Server

### Development Mode

```bash
# Fast API auto-reload
uvicorn main:app --reload

# Or with specific port
uvicorn main:app --reload --port 8000

# Or with host binding
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Server will start at: `http://localhost:8000`

## 📖 API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🎯 API Endpoints

### 1. Health Check
```http
GET /
```
**Response:**
```json
{
  "status": "healthy",
  "instagram_account_id": "123456789",
  "api_version": "v18.0",
  "upload_dir": "/path/to/uploads",
  "config_status": {...}
}
```

### 2. Upload & Post to Instagram
```http
POST /upload-post
Content-Type: multipart/form-data

file: <image_file>
caption: <post_caption>
```

**Response:**
```json
{
  "success": true,
  "creation_id": "container_id_123",
  "post_id": "instagram_post_id_456",
  "message": "Post published successfully!",
  "instagram_post_url": "https://www.instagram.com/p/ABC123/",
  "uploaded_image_url": "https://i.ibb.co/..."
}
```

## 🖼️ Image Requirements

### Supported Formats
- JPEG (.jpg, .jpeg)
- PNG (.png)
- WebP (.webp)
- Maximum file size: 10MB

### Automatic Aspect Ratios

Your images will be automatically adjusted to one of these formats:

| Format | Dimensions | Use Case |
|--------|-----------|----------|
| **Square** | 1080×1080 | Feed posts, main content |
| **Portrait** | 1080×1350 | Vertical content, Stories |
| **Landscape** | 1080×566 | Wide scenes, videos |

**How it works:**
1. You upload any size/format image
2. System detects the closest aspect ratio match
3. Smart cropping removes excess (no stretching)
4. Resized to optimal Instagram dimensions
5. Converted to JPEG for best compatibility

## 🔑 Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Required - Instagram
INSTAGRAM_ACCOUNT_ID=your_business_account_id
PAGE_ACCESS_TOKEN=your_facebook_page_access_token

# Required - Image Hosting (choose one)
IMGBB_API_KEY=your_imgbb_api_key
# OR
IMGUR_CLIENT_ID=your_imgur_client_id

# Optional - API Settings
GRAPH_API_VERSION=v18.0
GRAPH_API_BASE=https://graph.instagram.com
MAX_FILE_SIZE_MB=10
ALLOWED_EXTENSIONS=.jpg,.jpeg,.png,.webp
```

### Getting Credentials

#### Instagram Business Account
1. Go to [Meta Business Suite](https://business.facebook.com)
2. Create a Business Account (if you don't have one)
3. Add Instagram Account to your Business

#### Page Access Token
1. Visit [Facebook Developers](https://developers.facebook.com)
2. Create an App
3. Add Instagram Graph API
4. Go to Tools > Graph Explorer
5. Get a Page Access Token with these permissions:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`

#### Get Your Instagram Account ID
```bash
# Use this API call with your token:
GET https://graph.instagram.com/me/accounts?access_token=YOUR_TOKEN

# Find the instagram_business_account field
```

#### ImgBB API Key (Free)
1. Go to [ImgBB](https://api.imgbb.com)
2. Sign up (free account)
3. Get API key from your account dashboard

## 🧪 Testing

### 1. Using Web Interface (Easiest)
```
http://localhost:8000/static/test_upload.html
```

### 2. Using Swagger UI
```
http://localhost:8000/docs
```
- Click "Try it out"
- Upload an image file
- Add a caption
- Click "Execute"

### 3. Using cURL
```bash
curl -X POST "http://localhost:8000/upload-post" \
  -F "file=@/path/to/image.jpg" \
  -F "caption=Check out this amazing photo! 📸"
```

### 4. Using Python
```python
import requests

with open('image.jpg', 'rb') as f:
    files = {'file': f}
    data = {'caption': 'My awesome post! 🎉'}
    response = requests.post('http://localhost:8000/upload-post', files=files, data=data)
    print(response.json())
```

### 5. Using JavaScript/Fetch
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('caption', 'Great post!');

fetch('http://localhost:8000/upload-post', {
  method: 'POST',
  body: formData
})
.then(r => r.json())
.then(data => console.log(data))
.catch(e => console.error(e));
```

## 🏗️ Architecture

### Component Overview

```
┌─────────────────────────────────────┐
│         FastAPI Application         │
│           (main.py)                 │
└──────────────┬──────────────────────┘
               │
       ┌───────┴──────────┐
       │                  │
  ┌────▼────┐      ┌─────▼──────┐
  │ Services │      │  Models    │
  │          │      │            │
  │ Image    │      │ Pydantic   │
  │Instagram │      │ Schemas    │
  └────┬─────┘      └────────────┘
       │
       ├─────────────────────────────┐
       │                             │
  ┌────▼──────────┐      ┌──────────▼──┐
  │ Image Upload  │      │   Instagram │
  │ & Hosting     │      │   Graph API │
  │               │      │             │
  │ • Save file   │      │ • Create    │
  │ • Validate    │      │   container │
  │ • Crop/Resize │      │ • Publish   │
  │ • ImgBB/Imgur│      │ • Status    │
  └───────────────┘      └─────────────┘
```

## 📊 Request/Response Flow

```
1. User uploads image + caption
   ↓
2. Validate file type & size
   ↓
3. Open image with PIL
   ↓
4. Detect aspect ratio
   ↓
5. Smart crop to ratio
   ↓
6. Resize to Instagram dimensions
   ↓
7. Convert to JPEG (quality 95)
   ↓
8. Upload to ImgBB/Imgur
   ↓
9. Get hosted image URL
   ↓
10. Create Instagram media container
    ↓
11. Check container status
    ↓
12. Publish to Instagram
    ↓
13. Delete temporary file
    ↓
14. Return success with Instagram URL
```

## 🚨 Troubleshooting

| Error | Solution |
|-------|----------|
| `Access token not configured` | Set `PAGE_ACCESS_TOKEN` in `.env` |
| `INSTAGRAM_ACCOUNT_ID not found` | Verify account ID in Meta Business Suite |
| `ImgBB API key not configured` | Set `IMGBB_API_KEY` in `.env` |
| `Invalid image dimensions` | Image doesn't match Instagram ratios |
| `File too large` | Max file size is 10MB (change in `.env`) |
| `Invalid file type` | Only JPG, PNG, WebP supported |
| `Module not found` | Run `pip install -r requirements.txt` |

## 🔐 Security Best Practices

- ✅ Never commit `.env` file (add to `.gitignore`)
- ✅ Rotate access tokens regularly
- ✅ Use environment variables for all secrets
- ✅ Enable HTTPS in production
- ✅ Implement rate limiting
- ✅ Add authentication to production endpoints
- ✅ Sanitize user input/captions
- ✅ Delete uploaded files after processing

## 🐳 Docker Deployment

### Build Image
```bash
docker build -t instagram-autopost .
```

### Run Container
```bash
docker run -p 8000:8000 \
  -e INSTAGRAM_ACCOUNT_ID=your_id \
  -e PAGE_ACCESS_TOKEN=your_token \
  -e IMGBB_API_KEY=your_key \
  instagram-autopost
```

## 📦 Dependencies

```
fastapi==0.115.5          # Web framework
uvicorn[standard]==0.32.1 # ASGI server
pydantic==2.10.3          # Data validation
requests==2.32.3          # HTTP client
aiofiles==24.1.0          # Async file handling
python-multipart==0.0.20  # Form data parsing
python-dotenv==1.0.1      # Environment variables
Pillow==10.1.0            # Image processing
```

## 📄 License

MIT License - Feel free to use and modify!

## 🤝 Contributing

Found a bug? Have a feature idea? Open an issue or submit a PR!

## 📞 Quick Links

- [Instagram Graph API Docs](https://developers.facebook.com/docs/instagram-graph-api)
- [ImgBB API](https://api.imgbb.com)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Meta Business Suite](https://business.facebook.com)