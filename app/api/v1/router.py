from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, files, friends

api_router = APIRouter()

# Include routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(friends.router, prefix="/friends", tags=["friends"]) 