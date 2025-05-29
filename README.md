# Behex API

A production-ready FastAPI application with authentication, file management, and microservices-ready architecture.

## 🏗️ Architecture

The application is split into two main components for better modularity and easier management:

### Infrastructure Services (`docker-compose.infrastructure.yml`)
- **PostgreSQL 16**: Primary database with async support
- **Redis 7**: Caching and session storage  
- **MinIO**: S3-compatible object storage for files

### Application Services (`docker-compose.yml`)
- **FastAPI App**: Main application with API endpoints
- **Alembic**: Database migrations
- **Uvicorn**: ASGI server with hot reload

## 🚀 Quick Start

### Option 1: One-Command Setup (Recommended)
```bash
chmod +x setup.sh && ./setup.sh
```

### Option 2: Manual Setup

#### 1. Environment Setup
```bash
# The setup script will create .env automatically, or create it manually:
cp .env.example .env  # If you have .env.example
# Edit the .env file with your configuration
nano .env
```

#### 2. Start Infrastructure
```bash
# Start all infrastructure services
make infrastructure

# Or manually:
docker network create behex_network
docker-compose -f docker-compose.infrastructure.yml up -d
```

#### 3. Start Application
```bash
# Start the application
make app

# Or manually:
docker-compose up -d
```

## 📋 Available Commands

```bash
make help                 # Show all available commands
make infrastructure      # Start infrastructure services only
make infrastructure-down # Stop infrastructure services
make app                 # Start application only
make app-down            # Stop application only
make all                 # Start everything
make down                # Stop all services
make clean               # Clean up everything (containers, volumes, networks)
make app-logs           # View application logs
make infrastructure-logs # View infrastructure logs
make build              # Build application container
make restart            # Quick restart of application
make dev-setup          # Complete development environment setup
```

## 🗄️ Database Operations

```bash
make db-migrate         # Run pending migrations
make db-migration       # Create new migration (interactive)
make db-downgrade       # Rollback last migration
```

## 🌐 Service Endpoints

- **API**: http://localhost:10000
- **API Documentation**: http://localhost:10000/docs
- **Redoc Documentation**: http://localhost:10000/redoc
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379
- **MinIO API**: localhost:9000
- **MinIO Console**: http://localhost:9001

## 🔧 API Features

### Authentication
- **Email/Password Registration & Login**
- **Google OAuth Integration**
- **JWT Access & Refresh Tokens**
- **Password Reset via Email**

### File Management
- **Upload/Download Files**
- **File Metadata Storage**
- **Shareable Links**
- **Redis Caching**
- **Size & Extension Validation**

### User Management
- **Profile Management**
- **Account Operations**
- **Admin Controls**

## 🏁 Benefits of This Architecture

1. **🔄 Modular**: Infrastructure and application can be managed independently
2. **📈 Scalable**: Easy to scale services separately
3. **🛠️ Development Friendly**: Start only what you need for development
4. **🚀 Production Ready**: Infrastructure services can run on different hosts
5. **🐛 Easy Debugging**: Isolate issues to specific service layers
6. **💾 Resource Efficient**: Different resource allocation for different services

## 👨‍💻 Development Workflow

```bash
# First time setup
chmod +x setup.sh && ./setup.sh

# Daily development workflow
make restart              # Just restart the app
make app-logs            # Check application logs

# Working on database changes
make db-migration        # Create migration
make db-migrate          # Apply migration

# Infrastructure maintenance
make infrastructure-logs # Check infrastructure logs
make infrastructure      # Restart infrastructure if needed
```

## 🏭 Production Deployment

### Docker Swarm / Single Host
```bash
# Production environment file
cp .env .env.production
# Edit .env.production with production values

# Start infrastructure
docker-compose -f docker-compose.infrastructure.yml --env-file .env.production up -d

# Start application
docker-compose --env-file .env.production up -d
```

### Multi-Host Deployment
1. **Infrastructure Host**: Deploy `docker-compose.infrastructure.yml`
2. **Application Host**: Deploy `docker-compose.yml` 
3. **Network**: Configure Docker networks or service discovery for cross-host communication

### Kubernetes
The current setup can be easily converted to Kubernetes manifests:
- Infrastructure services → StatefulSets
- Application → Deployment
- Networking → Services & Ingress

## 🔍 Troubleshooting

### Check Service Status
```bash
# Infrastructure services
docker-compose -f docker-compose.infrastructure.yml ps

# Application services
docker-compose ps

# All containers
docker ps
```

### View Logs
```bash
# Application logs
make app-logs

# Infrastructure logs
make infrastructure-logs

# Specific service logs
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f minio
```

### Common Issues

#### Database Connection Issues
```bash
# Check if postgres is running
docker-compose -f docker-compose.infrastructure.yml ps postgres

# Check postgres logs
docker-compose -f docker-compose.infrastructure.yml logs postgres

# Test connection manually
docker-compose -f docker-compose.infrastructure.yml exec postgres psql -U behex_user -d behex_db
```

#### Redis Connection Issues
```bash
# Check redis status
docker-compose -f docker-compose.infrastructure.yml ps redis

# Test redis connection
docker-compose -f docker-compose.infrastructure.yml exec redis redis-cli -a redis_password_123 ping
```

#### MinIO Issues
```bash
# Check MinIO status
docker-compose -f docker-compose.infrastructure.yml ps minio

# Access MinIO console
# Open http://localhost:9001 in browser
```

### Reset Everything
```bash
make clean              # Remove everything
./setup.sh             # Start fresh
```

## 📁 Project Structure

```
behex/
├── app/                          # FastAPI application
│   ├── api/                      # API routes
│   │   ├── deps.py              # Dependencies
│   │   └── v1/                  # API v1
│   │       ├── endpoints/       # Route handlers
│   │       └── router.py        # Route registration
│   ├── core/                    # Core functionality
│   │   ├── config.py           # Configuration
│   │   ├── database.py         # Database setup
│   │   ├── redis.py            # Redis setup
│   │   ├── minio.py            # MinIO setup
│   │   ├── security.py         # Authentication
│   │   └── email.py            # Email service
│   ├── models/                  # SQLAlchemy models
│   ├── schemas/                 # Pydantic schemas
│   ├── services/                # Business logic
│   ├── repositories/            # Data access layer
│   ├── utils/                   # Utilities
│   └── main.py                  # FastAPI app
├── alembic/                     # Database migrations
├── docker-compose.yml           # Application services
├── docker-compose.infrastructure.yml  # Infrastructure services
├── Dockerfile                   # Application container
├── requirements.txt             # Python dependencies
├── Makefile                     # Development commands
├── setup.sh                     # Setup script
└── README.md                    # This file
```

## 🔐 Environment Variables

The `.env` file contains all configuration. Key variables:

```bash
# Security
SECRET_KEY=your-secret-key-change-this-in-production
JWT_SECRET_KEY=jwt-secret-key-change-this-in-production

# Database
DB_HOST=behex_postgres           # Container name for database
DB_USER=behex_user
DB_PASSWORD=behex_password
DB_NAME=behex_db

# Services
REDIS_HOST=behex_redis           # Container name for Redis
MINIO_ENDPOINT=behex_minio:9000  # Container name for MinIO

# External services
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

## 📈 Scaling & Performance

### Horizontal Scaling
- **Application**: Scale multiple app containers behind a load balancer
- **Database**: Use read replicas for PostgreSQL
- **Cache**: Use Redis Cluster for high availability
- **Storage**: Use MinIO in distributed mode

### Monitoring
Add monitoring services:
```yaml
# Add to docker-compose.infrastructure.yml
  prometheus:
    image: prom/prometheus
    ports: ["9090:9090"]
  
  grafana:
    image: grafana/grafana
    ports: ["3000:3000"]
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Run tests: `make test` (when available)
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details. 



# Create new migration after model changes
make db-migration
# or manually:
docker-compose exec app alembic revision --autogenerate -m "Your message"

# Apply pending migrations
make db-migrate  
# or manually:
docker-compose exec app alembic upgrade head

# View migration history
docker-compose exec app alembic history

# Rollback last migration (if needed)
make db-downgrade
# or manually:
docker-compose exec app alembic downgrade -1