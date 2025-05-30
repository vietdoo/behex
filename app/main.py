from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.redis import redis_client
from app.core.minio import minio_client
from app.api.v1.router import api_router
from app.api.v1.endpoints.websocket import websocket_endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    print("Starting up...")
    # Connect to Redis
    await redis_client.connect()
    # Ensure MinIO bucket exists
    await minio_client.ensure_bucket_exists()
    
    yield
    
    # Shutdown
    print("Shutting down...")
    # Disconnect from Redis
    await redis_client.disconnect()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

# WebSocket endpoint for chat
app.websocket("/ws/chat")(websocket_endpoint)

# Root endpoint
@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs",
        "redoc": "/api/redoc",
        "health": "/health",
        "api": "/api/v1",
        "websocket": "/ws/chat"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    # Check Redis connection
    redis_status = "healthy"
    try:
        await redis_client.set("health_check", "ok", expire=10)
    except:
        redis_status = "unhealthy"
    
    # Check MinIO connection
    minio_status = "healthy"
    try:
        await minio_client.ensure_bucket_exists()
    except:
        minio_status = "unhealthy"
    
    return {
        "status": "healthy" if redis_status == "healthy" and minio_status == "healthy" else "degraded",
        "services": {
            "redis": redis_status,
            "minio": minio_status
        }
    } 