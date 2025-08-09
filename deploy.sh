#!/bin/bash
# Server Deployment Script for FileShare Portal

echo "🚀 Starting FileShare Portal deployment..."

# 1. Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# 2. Run database migrations (SQLite - no setup needed)
echo "🔄 Setting up SQLite database and running migrations..."
python migrate_db.py

# 3. Create demo user
echo "👤 Creating demo user..."
python create_demo_user.py

# 4. Create uploads directory
echo "📁 Creating uploads directory..."
mkdir -p uploads

# 5. Set permissions (Linux/Unix only)
if [ "$(uname)" != "MINGW64_NT"* ]; then
    echo "🔒 Setting permissions..."
    chmod 755 uploads
    chmod +x run_server.py
fi

echo "✅ Deployment complete!"
echo ""
echo "🎉 FileShare Portal is ready to run!"
echo "💾 Database: SQLite (file_share.db) - portable and simple!"
echo "📝 Demo credentials:"
echo "   Username: demo"
echo "   Password: demo123"
echo ""
echo "🚀 To start the server, run:"
echo "   python run_server.py"
echo "   or"
echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000"
