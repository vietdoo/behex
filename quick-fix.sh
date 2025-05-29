#!/bin/bash

echo "🔧 Quick fix: Restarting services in proper order..."

# Stop everything completely
echo "⏹️  Stopping all services..."
docker-compose down
docker-compose -f docker-compose.infrastructure.yml down

# Remove any old containers that might be conflicting
echo "🧹 Cleaning up old containers..."
docker rm -f behex_app behex_postgres behex_redis behex_minio behex-app behex-postgres behex-redis behex-minio 2>/dev/null || true

# Ensure network exists
echo "🔧 Ensuring network exists..."
docker network rm behex_network 2>/dev/null || true
docker network create behex_network

# Start infrastructure first and wait
echo "🐳 Starting infrastructure services..."
docker-compose -f docker-compose.infrastructure.yml up -d

# Wait longer for infrastructure to be fully ready
echo "⏳ Waiting for infrastructure to be fully ready..."
sleep 20

# Test connectivity to infrastructure
echo "🔍 Testing infrastructure connectivity..."
echo "Testing PostgreSQL..."
until docker-compose -f docker-compose.infrastructure.yml exec postgres pg_isready -U behex_user -d behex_db 2>/dev/null; do
  echo "Waiting for PostgreSQL..."
  sleep 2
done

echo "Testing Redis..."
until docker-compose -f docker-compose.infrastructure.yml exec redis redis-cli -a redis_password_123 ping 2>/dev/null | grep -q PONG; do
  echo "Waiting for Redis..."
  sleep 2
done

echo "Testing MinIO..."
until curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; do
  echo "Waiting for MinIO..."
  sleep 2
done

echo "✅ All infrastructure services are ready!"

# Now start the application
echo "🚀 Starting application..."
docker-compose up -d

echo ""
echo "🎉 Quick fix complete!"
echo ""
echo "📊 Service Status:"
echo "Infrastructure:"
docker-compose -f docker-compose.infrastructure.yml ps
echo ""
echo "Application:"
docker-compose ps

echo ""
echo "📖 Monitor application startup:"
echo "  docker-compose logs -f app"
echo ""
echo "🌐 Should be available at:"
echo "  • API: http://localhost:10000"
echo "  • API Docs: http://localhost:10000/docs" 