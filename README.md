# 🚀 FileShare Portal

A modern, secure file-sharing web application built with **FastAPI** and featuring a responsive UI with **Tailwind CSS**.

## ✨ Features

### 🔐 **User Authentication**
- **Registration & Login** with secure password hashing (bcrypt)
- **JWT-based authentication** for session management
- **User dashboard** with file statistics and activity overview

### 📁 **File Management**
- **Secure file uploads** with validation (type, size limits)
- **File preview** support for images, PDFs, and text files
- **Time-limited sharing** with optional expiry settings
- **Download tracking** and analytics
- **Private file access** - users can only see their own files

### 🎨 **Modern UI/UX**
- **Responsive design** with Tailwind CSS
- **Mobile-friendly** interface
- **Drag-and-drop** file uploads
- **Real-time notifications** and feedback
- **Intuitive navigation** with breadcrumbs

### 🛡️ **Security Features**
- **File type validation** with configurable allowed extensions
- **File size limits** to prevent abuse
- **User isolation** - files are private to uploaders
- **Secure file storage** with unique IDs
- **Public download links** for easy sharing

## 🚀 **Quick Start**

### 1. **Setup**
```bash
# Install dependencies
pip install -r requirements.txt
```

### 2. **Initialize Database**
```bash
# Setup SQLite database and create demo user
python migrate_db.py
python create_demo_user.py
```

### 3. **Run the Application**
```bash
# Start the development server
uvicorn app.main:app --reload

# Or for production
python run_server.py
```

The application will be available at: **http://127.0.0.1:8000**

### 4. **Super Easy Deployment**
```bash
# One command deployment
./deploy.sh    # Linux/Unix
deploy.bat     # Windows
```

## 🧪 **Testing**

### **Demo Credentials**
- **Username**: `demo`
- **Password**: `demo123`

## 📊 **Features Overview**

| Feature | Status | Description |
|---------|--------|-------------|
| ✅ User Registration | Complete | Secure user account creation |
| ✅ User Authentication | Complete | JWT-based login system |
| ✅ File Upload | Complete | Drag-and-drop with validation (60+ file types) |
| ✅ File Download | Complete | Public/private download links |
| ✅ File Preview | Complete | Images, PDFs, videos, audio, text files |
| ✅ File Management | Complete | List, delete, and organize files |
| ✅ Public/Private Sharing | Complete | Toggle file visibility settings |
| ✅ User Dashboard | Complete | Statistics and recent activity |
| ✅ Responsive UI | Complete | Mobile-friendly interface |
| ✅ Time-Limited Sharing | Complete | Optional file expiry |
| ✅ Download Tracking | Complete | Track file access |
| ✅ Enhanced File Support | Complete | 60+ file types (docs, media, archives) |
| ✅ SQLite Database | Complete | Simple, portable, no setup required |

---

**Happy file sharing! 🎉**
4327d3310305579ad6b9390cfb1cd199f2089f1c