# 📁 Folder Structure

```
instagram-auto-post/
│
├── 📄 main.py                    # ⭐ Main FastAPI app (START HERE)
├── 📄 requirements.txt           # Python dependencies
├── 📄 .env.example              # Environment variables template
├── 📄 .gitignore                # Git ignore rules
├── 📄 README.md                 # Documentation
│
├── 📂 app/                       # Application code
│   ├── __init__.py              # Module initialization
│   ├── config.py                # ⚙️ Settings & configuration
│   ├── models.py                # 📋 Pydantic models (request/response)
│   └── services.py              # 🔧 Business logic
│       ├── ImageService         # - Handle file uploads
│       └── InstagramService     # - Instagram API calls
│
├── 📂 static/                    # Static files
│   └── test_upload.html         # 🧪 Web test interface
│
├── 📂 tests/                     # Test scripts
│   └── test_api.py              # Python test script
│
└── 📂 uploads/                   # Temporary uploads (auto-created)
    └── (temp files)
```

## 🎯 File Purposes

### Core Files

- **main.py** 
  - FastAPI application
  - All API endpoints defined here
  - Run this to start the server

- **app/config.py**
  - Loads environment variables
  - Settings management
  - Configuration validation

- **app/models.py**
  - Pydantic models for type validation
  - Request/response schemas

- **app/services.py**
  - **ImageService**: Save files, upload to cloud
  - **InstagramService**: Create & publish posts

### Testing Files

- **static/test_upload.html**
  - Beautiful web interface
  - Open in browser to test uploads

- **tests/test_api.py**
  - Python test script
  - Run to check API health

### Configuration Files

- **.env.example**
  - Template for environment variables
  - Copy to `.env` and fill in your credentials

- **requirements.txt**
  - Python packages needed
  - Install with: `pip install -r requirements.txt`

## 🚀 How It Works Together

1. **User hits endpoint** → `main.py` receives request
2. **main.py calls** → `ImageService` to handle file
3. **ImageService** → Saves file, uploads to ImgBB
4. **main.py calls** → `InstagramService` to post
5. **InstagramService** → Creates container, publishes
6. **Response sent back** → Success/error message

## 📝 Key Points

✅ Clean separation of concerns
✅ Easy to test and maintain  
✅ Settings in one place (config.py)
✅ Business logic isolated (services.py)
✅ Type-safe with Pydantic (models.py)