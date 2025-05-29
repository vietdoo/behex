from typing import Optional
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from google.auth.transport import requests
from google.oauth2 import id_token
import secrets

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
    create_password_reset_token,
    verify_password_reset_token
)
from app.core.config import settings
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserOAuthCreate
from app.schemas.auth import Token
from app.models.user import User
from app.services.email import EmailService


class AuthService:
    def __init__(self, db: AsyncSession):
        self.user_repo = UserRepository(db)
        self.email_service = EmailService()

    async def register(self, user_data: UserCreate) -> Optional[User]:
        """Register a new user"""
        # Check if user already exists
        existing_user = await self.user_repo.get_by_email(user_data.email)
        if existing_user:
            return None
        
        existing_username = await self.user_repo.get_by_username(user_data.username)
        if existing_username:
            return None

        # Create user
        user = await self.user_repo.create(user_data)
        
        if user:
            # Send welcome email (don't await to avoid blocking)
            await self.email_service.send_welcome_email(user.email, user.full_name or user.username)
        
        return user

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password"""
        user = await self.user_repo.get_by_email(email)
        if not user or not user.hashed_password:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        if not user.is_active:
            return None
        
        return user

    async def create_tokens(self, user: User) -> Token:
        """Create access and refresh tokens for user"""
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    async def refresh_access_token(self, refresh_token: str) -> Optional[Token]:
        """Refresh access token using refresh token"""
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        user = await self.user_repo.get_by_id(int(user_id))
        if not user or not user.is_active:
            return None
        
        return await self.create_tokens(user)

    async def google_auth(self, credential: str) -> Optional[tuple[User, Token]]:
        """Authenticate or register user with Google OAuth"""
        try:
            # Verify the Google ID token
            idinfo = id_token.verify_oauth2_token(
                credential,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
            
            # Get user info from token
            email = idinfo.get("email")
            name = idinfo.get("name")
            google_id = idinfo.get("sub")
            
            if not email or not google_id:
                return None
            
            # Check if user exists with this Google ID
            user = await self.user_repo.get_by_oauth("google", google_id)
            
            if not user:
                # Check if user exists with this email
                user = await self.user_repo.get_by_email(email)
                
                if user:
                    # Link existing account with Google
                    user.oauth_provider = "google"
                    user.oauth_provider_id = google_id
                    await self.user_repo.db.commit()
                else:
                    # Create new user
                    username = email.split("@")[0] + "_" + secrets.token_hex(3)
                    oauth_data = UserOAuthCreate(
                        email=email,
                        username=username,
                        full_name=name,
                        oauth_provider="google",
                        oauth_provider_id=google_id
                    )
                    user = await self.user_repo.create_oauth_user(oauth_data)
                    
                    if user:
                        await self.email_service.send_welcome_email(user.email, user.full_name or user.username)
            
            if not user or not user.is_active:
                return None
            
            # Create tokens
            tokens = await self.create_tokens(user)
            return user, tokens
            
        except ValueError:
            # Invalid token
            return None

    async def request_password_reset(self, email: str) -> bool:
        """Request password reset for user"""
        user = await self.user_repo.get_by_email(email)
        if not user:
            # Don't reveal if user exists
            return True
        
        # Create reset token
        reset_token = create_password_reset_token(email)
        
        # Send reset email
        await self.email_service.send_password_reset_email(email, reset_token)
        
        return True

    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset user password with token"""
        email = verify_password_reset_token(token)
        if not email:
            return False
        
        user = await self.user_repo.get_by_email(email)
        if not user:
            return False
        
        return await self.user_repo.update_password(user.id, new_password) 