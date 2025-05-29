#!/bin/bash

echo "🚀 Setting up Behex API development environment..."

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env << 'EOF'
# Application Settings
SECRET_KEY=your-secret-key-change-this-in-production
JWT_SECRET_KEY=jwt-secret-key-change-this-in-production
APP_NAME=BehexAPI
APP_VERSION=1.0.0
DEBUG=true
ENVIRONMENT=development

# Database Configuration
DB_USER=behex_user
DB_PASSWORD=behex_password
DB_NAME=behex_db
DB_HOST=localhost
DB_PORT=5432

# Redis Configuration
REDIS_PASSWORD=redis_password_123
REDIS_HOST=localhost
REDIS_PORT=6379

# MinIO Configuration
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
MINIO_BUCKET_NAME=behex-files
MINIO_ENDPOINT=localhost:9000
MINIO_SECURE=false

# JWT Configuration
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Google OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_FROM_NAME=Behex

# CORS Configuration
BACKEND_CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# File Upload Configuration
MAX_FILE_SIZE_MB=100
ALLOWED_EXTENSIONS=.jpg,.jpeg,.png,.pdf,.doc,.docx,.zip
EOF
    echo "✅ .env file created successfully!"
else
    echo "📋 .env file already exists, skipping creation..."
fi

# Make the script executable
chmod +x setup.sh

echo "🔧 Setting up Docker network..."
docker network ls | grep behex_network > /dev/null || docker network create behex_network

echo "🐳 Starting infrastructure services..."
docker-compose -f docker-compose.infrastructure.yml up -d

echo "⏳ Waiting for infrastructure to be ready..."
sleep 15

echo "🔨 Building and starting application..."
docker-compose up --build -d

echo ""
echo "🎉 Setup complete!"
echo ""
echo "🌐 Service URLs:"
echo "  • API: http://localhost:8000"
echo "  • API Docs: http://localhost:8000/docs"
echo "  • MinIO Console: http://localhost:9001"
echo "  • PostgreSQL: localhost:5432"
echo "  • Redis: localhost:6379"
echo ""
echo "📖 Useful commands:"
echo "  • make help - Show all available commands"
echo "  • make app-logs - View application logs"
echo "  • make infrastructure-logs - View infrastructure logs"
echo "  • make restart - Restart the application"
echo "  • make down - Stop all services"
echo "" 