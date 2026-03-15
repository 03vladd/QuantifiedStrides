"""
Database and auth dependency injection for FastAPI.

Provides:
  get_db()             — async SQLAlchemy session
  get_current_user_id()— extracts user_id from X-User-Id header
                         (dev convenience; swap for JWT decode in production)

Usage in a router:
    @router.get("/")
    async def my_endpoint(
        db: AsyncSession = Depends(get_db),
        user_id: int = Depends(get_current_user_id),
    ):
        ...
"""

from collections.abc import AsyncGenerator

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.settings import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,   # drop stale connections before use
    echo=settings.db_echo,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user_id(x_user_id: int = Header(...)) -> int:
    """
    Extracts the authenticated user_id from the X-User-Id request header.

    Development: send `X-User-Id: 1` in every request.
    Production:  replace this function body with JWT token decoding.
    """
    if x_user_id < 1:
        raise HTTPException(status_code=401, detail="Invalid user identity")
    return x_user_id
