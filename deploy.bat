@echo off
REM Windows Server Deployment Script for FileShare Portal

echo 🚀 Starting FileShare Portal deployment on Windows...

REM 1. Install Python dependencies
echo 📦 Installing Python dependencies...
pip install -r requirements.txt

REM 2. Setup SQLite database (no additional setup needed)
echo 🗄️ Setting up SQLite database...
python migrate_db.py

REM 3. Create demo user
echo 👤 Creating demo user...
python create_demo_user.py

REM 4. Create uploads directory
echo 📁 Creating uploads directory...
if not exist "uploads" mkdir uploads

echo ✅ Deployment complete!
echo.
echo 🎉 FileShare Portal is ready to run!
echo 💾 Database: SQLite (file_share.db) - portable and simple!
echo 📝 Demo credentials:
echo    Username: demo
echo    Password: demo123
echo.
echo 🚀 To start the server, run:
echo    python run_server.py
echo    or
echo    uvicorn app.main:app --host 0.0.0.0 --port 8000

pause
