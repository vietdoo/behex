#!/bin/bash

echo "🔧 Fixing the application with updated dependencies and container names..."

# Stop all current containers (including old names)
echo "⏹️  Stopping all current containers..."
docker-compose down
docker-compose -f docker-compose.infrastructure.yml down

# Remove any containers with old names
echo "🧹 Cleaning up old containers..."
docker rm -f behex_app behex_postgres behex_redis behex_minio 2>/dev/null || true

# Create/ensure network exists
echo "🔧 Setting up Docker network..."
docker network ls | grep behex_network > /dev/null || docker network create behex_network

# Start infrastructure with new names
echo "🐳 Starting infrastructure services..."
docker-compose -f docker-compose.infrastructure.yml up -d

# Wait for infrastructure to be ready
echo "⏳ Waiting for infrastructure to be ready..."
sleep 15

# Rebuild the app with new dependencies and start it
echo "🔨 Rebuilding and starting application..."
docker-compose build app --no-cache
docker-compose up -d

echo ""
echo "✅ Fix complete!"
echo ""
echo "📊 Checking all service status..."
sleep 5
echo "Infrastructure Services:"
docker-compose -f docker-compose.infrastructure.yml ps
echo ""
echo "Application Services:"
docker-compose ps

echo ""
echo "📖 View logs with:"
echo "  make app-logs"
echo "  make infrastructure-logs"
echo ""
echo "🌐 Application should be available at:"
echo "  • API: http://localhost:8000"
echo "  • API Docs: http://localhost:8000/docs"
echo "  • MinIO Console: http://localhost:9001" 