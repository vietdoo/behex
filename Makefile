.PHONY: help infrastructure infrastructure-down app app-down app-logs infrastructure-logs all down clean setup

help:
	@echo "🚀 Behex API - Available Commands:"
	@echo ""
	@echo "🛠️  Setup & Management:"
	@echo "  setup             - Initial setup (runs setup.sh)"
	@echo "  infrastructure     - Start infrastructure services (PostgreSQL, Redis, MinIO)"
	@echo "  infrastructure-down - Stop infrastructure services"
	@echo "  app               - Start application service"
	@echo "  app-down          - Stop application service"
	@echo "  all               - Start all services"
	@echo "  down              - Stop all services"
	@echo "  clean             - Remove all containers and volumes"
	@echo "  build             - Build application container"
	@echo ""
	@echo "📊 Monitoring & Logs:"
	@echo "  app-logs          - View application logs"
	@echo "  infrastructure-logs - View infrastructure logs"
	@echo "  status            - Show status of all services"
	@echo ""
	@echo "🗄️  Database Operations:"
	@echo "  db-migrate        - Run pending migrations"
	@echo "  db-migration      - Create new migration (interactive)"
	@echo "  db-downgrade      - Rollback last migration"
	@echo "  db-reset          - Reset database (WARNING: destroys data)"
	@echo ""
	@echo "🔄 Development:"
	@echo "  dev-setup         - Complete development environment setup"
	@echo "  restart           - Quick restart of application"
	@echo "  shell             - Access application container shell"
	@echo ""
	@echo "🌐 Service URLs:"
	@echo "  • API: http://localhost:8000"
	@echo "  • API Docs: http://localhost:8000/docs"
	@echo "  • MinIO Console: http://localhost:9001"

# Initial setup
setup:
	@echo "🚀 Running initial setup..."
	@chmod +x setup.sh
	@./setup.sh

# Create the external network if it doesn't exist
create-network:
	@docker network ls | grep behex_network > /dev/null || docker network create behex_network

# Infrastructure services
infrastructure: create-network
	@echo "🐳 Starting infrastructure services..."
	@docker-compose -f docker-compose.infrastructure.yml up -d
	@echo "✅ Infrastructure services started!"
	@echo "📊 Service Status:"
	@docker-compose -f docker-compose.infrastructure.yml ps
	@echo ""
	@echo "🌐 Available at:"
	@echo "  • PostgreSQL: localhost:5432"
	@echo "  • Redis: localhost:6379"
	@echo "  • MinIO API: localhost:9000"
	@echo "  • MinIO Console: http://localhost:9001"

infrastructure-down:
	@echo "⏹️  Stopping infrastructure services..."
	@docker-compose -f docker-compose.infrastructure.yml down

infrastructure-logs:
	@docker-compose -f docker-compose.infrastructure.yml logs -f

# Application services
app: create-network
	@echo "🚀 Starting application..."
	@docker-compose up -d
	@echo "✅ Application started!"
	@echo "📊 Service Status:"
	@docker-compose ps
	@echo ""
	@echo "🌐 Application available at:"
	@echo "  • API: http://localhost:8000"
	@echo "  • API Docs: http://localhost:8000/docs"

app-down:
	@echo "⏹️  Stopping application..."
	@docker-compose down

app-logs:
	@docker-compose logs -f

# Status check
status:
	@echo "📊 Infrastructure Services:"
	@docker-compose -f docker-compose.infrastructure.yml ps
	@echo ""
	@echo "📊 Application Services:"
	@docker-compose ps

# Combined commands
all: infrastructure
	@echo "⏳ Waiting for infrastructure to be ready..."
	@sleep 10
	@make app

down: app-down infrastructure-down

# Build
build:
	@echo "🔨 Building application container..."
	@docker-compose build

# Clean up everything
clean: down
	@echo "🧹 Cleaning up everything..."
	@docker-compose -f docker-compose.infrastructure.yml down -v
	@docker-compose down -v
	@docker system prune -f
	@docker network rm behex_network 2>/dev/null || true
	@echo "✅ Cleanup complete!"

# Development workflow
dev-setup: infrastructure
	@echo "⏳ Waiting for infrastructure to be ready..."
	@sleep 15
	@make app
	@echo ""
	@echo "🎉 Development environment ready!"
	@echo ""
	@echo "🌐 Available Services:"
	@echo "  • API: http://localhost:8000"
	@echo "  • API Docs: http://localhost:8000/docs"
	@echo "  • MinIO Console: http://localhost:9001"
	@echo ""
	@echo "📖 Next steps:"
	@echo "  • View logs: make app-logs"
	@echo "  • Restart app: make restart"
	@echo "  • Stop all: make down"

# Database operations
db-migrate:
	@echo "🔄 Running database migrations..."
	@docker-compose exec app alembic upgrade head
	@echo "✅ Migrations complete!"

db-migration:
	@read -p "📝 Enter migration message: " message; \
	echo "🔄 Creating migration: $$message"; \
	docker-compose exec app alembic revision --autogenerate -m "$$message"

db-downgrade:
	@echo "⚠️  Rolling back last migration..."
	@docker-compose exec app alembic downgrade -1
	@echo "✅ Rollback complete!"

db-reset:
	@echo "⚠️  WARNING: This will destroy all data!"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "🗑️  Resetting database..."; \
		docker-compose down; \
		docker-compose -f docker-compose.infrastructure.yml down -v; \
		docker volume rm behex_postgres_data 2>/dev/null || true; \
		make dev-setup; \
		echo "✅ Database reset complete!"; \
	else \
		echo "❌ Database reset cancelled."; \
	fi

# Development tools
shell:
	@echo "🐚 Accessing application container shell..."
	@docker-compose exec app bash

# Quick restart
restart: app-down app
	@echo "🔄 Application restarted!"

# Test infrastructure connectivity
test-infrastructure:
	@echo "🔍 Testing infrastructure connectivity..."
	@echo "📊 PostgreSQL:"
	@docker-compose -f docker-compose.infrastructure.yml exec postgres pg_isready -U behex_user -d behex_db || echo "❌ PostgreSQL not ready"
	@echo "📊 Redis:"
	@docker-compose -f docker-compose.infrastructure.yml exec redis redis-cli -a redis_password_123 ping || echo "❌ Redis not ready"
	@echo "📊 MinIO:"
	@curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1 && echo "✅ MinIO ready" || echo "❌ MinIO not ready" 