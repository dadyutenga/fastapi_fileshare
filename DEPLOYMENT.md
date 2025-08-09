# Server Deployment Guide for FileShare Portal

## 📋 Prerequisites on Your Server

1. **Python 3.8+** installed
2. **No database server needed** - uses SQLite (portable file database)
3. **Git** (optional, for easy updates)

## 🚀 Super Simple Deployment Steps

### 1. Upload Files to Server
Upload the entire project folder to your server

### 2. One-Command Setup

**Linux/Unix:**
```bash
chmod +x deploy.sh && ./deploy.sh
```

**Windows:**
```batch
deploy.bat
```

**Manual Setup:**
```bash
# Install dependencies
pip install -r requirements.txt

# Setup database and create demo user
python migrate_db.py
python create_demo_user.py

# Create uploads folder
mkdir uploads

# Start server
python run_server.py
```

### 3. Access Your Application

- **URL**: `http://your-server-ip:8000`
- **Demo Login**:
  - Username: `demo`
  - Password: `demo123`

## ⚙️ Configuration - SQLite (Super Simple!)

✅ **Database**: SQLite `file_share.db` (single file - no server needed!)  
✅ **Secret Key**: Strong 128-char key configured  
✅ **File Uploads**: 50MB limit, 60+ file types supported  
✅ **Security**: JWT authentication, password hashing  
✅ **Portable**: Just copy the folder and it works anywhere!

### 1. Install Python 3.8+
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv

# CentOS/RHEL
sudo yum install python3 python3-pip
```

### 2. Install MySQL Server
```bash
# Ubuntu/Debian
sudo apt install mysql-server
sudo mysql_secure_installation

# CentOS/RHEL
sudo yum install mysql-server
sudo systemctl start mysqld
sudo systemctl enable mysqld
```

### 3. Set MySQL root password
```bash
sudo mysql -u root -p
ALTER USER 'root'@'localhost' IDENTIFIED BY '1234567890';
FLUSH PRIVILEGES;
EXIT;
```

## Deployment Steps:

### 1. Upload your project folder to server
```bash
# Upload the entire 'test' folder to your server
scp -r /path/to/test user@yourserver:/var/www/fileshare/
```

### 2. Create virtual environment
```bash
cd /var/www/fileshare/test
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup MySQL database
```bash
python setup_mysql.py
```

### 5. Create uploads directory
```bash
mkdir -p uploads
chmod 755 uploads
```

### 6. Test the application
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 7. Setup systemd service (for production)
Create `/etc/systemd/system/fileshare.service`:
```ini
[Unit]
Description=FileShare Portal
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/fileshare/test
Environment=PATH=/var/www/fileshare/test/.venv/bin
ExecStart=/var/www/fileshare/test/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### 8. Start and enable service
```bash
sudo systemctl daemon-reload
sudo systemctl start fileshare
sudo systemctl enable fileshare
```

### 9. Setup Nginx (optional, for reverse proxy)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/fileshare/test/static/;
    }

    location /uploads/ {
        alias /var/www/fileshare/test/uploads/;
    }
}
```

## Security Notes:
- Change the SECRET_KEY in .env for production
- Use a strong MySQL password
- Consider using HTTPS with SSL certificates
- Set proper file permissions for uploads directory
- Configure firewall to only allow necessary ports

## Default Login:
- Username: demo
- Password: demo123
