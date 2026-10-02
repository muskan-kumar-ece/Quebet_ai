from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.user import User


class UserRepository:
    """Handles database operations for User entities."""

    async def get_by_id(self, db: AsyncSession, user_id: str) -> User | None:
        stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        email: str,
        hashed_password: str | None = None,
        name: str | None = None,
        plan: str = "free",
        skill_level: str = "beginner",
    ) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password,
            name=name,
            plan=plan,
            skill_level=skill_level,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


user_repo = UserRepository()
