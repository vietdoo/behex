from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.user import User
from app.schemas.user import UserCreate, UserOAuthCreate, UserUpdate
from app.core.security import get_password_hash


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_data: UserCreate) -> Optional[User]:
        """Create a new user"""
        try:
            db_user = User(
                email=user_data.email,
                username=user_data.username,
                full_name=user_data.full_name,
                hashed_password=get_password_hash(user_data.password),
                is_active=True,
                is_verified=False
            )
            self.db.add(db_user)
            await self.db.commit()
            await self.db.refresh(db_user)
            return db_user
        except IntegrityError:
            await self.db.rollback()
            return None

    async def create_oauth_user(self, user_data: UserOAuthCreate) -> Optional[User]:
        """Create a new OAuth user"""
        try:
            db_user = User(
                email=user_data.email,
                username=user_data.username,
                full_name=user_data.full_name,
                oauth_provider=user_data.oauth_provider,
                oauth_provider_id=user_data.oauth_provider_id,
                is_active=True,
                is_verified=True  # OAuth users are pre-verified
            )
            self.db.add(db_user)
            await self.db.commit()
            await self.db.refresh(db_user)
            return db_user
        except IntegrityError:
            await self.db.rollback()
            return None

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        query = select(User).filter(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        query = select(User).filter(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        query = select(User).filter(User.username == username)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_oauth(self, provider: str, provider_id: str) -> Optional[User]:
        """Get user by OAuth provider info"""
        query = select(User).filter(
            User.oauth_provider == provider,
            User.oauth_provider_id == provider_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update(self, user_id: int, user_data: UserUpdate) -> Optional[User]:
        """Update user"""
        user = await self.get_by_id(user_id)
        if not user:
            return None

        update_data = user_data.dict(exclude_unset=True)
        
        # Hash password if being updated
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

        for field, value in update_data.items():
            setattr(user, field, value)

        try:
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except IntegrityError:
            await self.db.rollback()
            return None

    async def delete(self, user_id: int) -> bool:
        """Delete user"""
        user = await self.get_by_id(user_id)
        if not user:
            return False

        await self.db.delete(user)
        await self.db.commit()
        return True

    async def update_password(self, user_id: int, new_password: str) -> bool:
        """Update user password"""
        user = await self.get_by_id(user_id)
        if not user:
            return False

        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()
        return True

    async def verify_user(self, user_id: int) -> bool:
        """Mark user as verified"""
        user = await self.get_by_id(user_id)
        if not user:
            return False

        user.is_verified = True
        await self.db.commit()
        return True 