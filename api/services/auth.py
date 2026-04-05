"""
Auth service — register, login, profile get/update.
"""

import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.settings import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> int:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return int(payload["sub"])


# ── register ──────────────────────────────────────────────────────────────────

async def register(
    db: AsyncSession,
    name: str,
    email: str,
    password: str,
    goal: str,
    gym_days_week: int,
    primary_sports: dict,
) -> dict:
    # Check email not already taken
    existing = await db.execute(
        text("SELECT user_id FROM users WHERE email = :email"),
        {"email": email},
    )
    if existing.fetchone():
        raise ValueError("Email already registered")

    password_hash = hash_password(password)

    verification_token = secrets.token_urlsafe(32)

    # Insert user
    result = await db.execute(
        text("""
            INSERT INTO users (name, email, password_hash, email_verified, verification_token)
            VALUES (:name, :email, :hash, FALSE, :token)
            RETURNING user_id
        """),
        {"name": name, "email": email, "hash": password_hash, "token": verification_token},
    )
    user_id = result.scalar_one()

    # Insert profile (JSONB needs explicit cast for asyncpg)
    import json
    await db.execute(
        text("""
            INSERT INTO user_profile (user_id, goal, gym_days_week, primary_sports)
            VALUES (:uid, :goal, :gym, CAST(:sports AS jsonb))
        """),
        {
            "uid": user_id,
            "goal": goal,
            "gym": gym_days_week,
            "sports": json.dumps(primary_sports),
        },
    )
    await db.commit()
    return {"user_id": user_id, "name": name, "email": email, "verification_token": verification_token}


# ── login ─────────────────────────────────────────────────────────────────────

async def login(db: AsyncSession, email: str, password: str) -> dict:
    result = await db.execute(
        text("SELECT user_id, name, password_hash, email_verified FROM users WHERE email = :email"),
        {"email": email},
    )
    row = result.fetchone()
    if not row or not verify_password(password, row.password_hash):
        raise ValueError("Invalid email or password")
    if not row.email_verified:
        raise ValueError("Please verify your email before signing in")
    token = create_token(row.user_id)
    return {"access_token": token, "token_type": "bearer", "user_id": row.user_id, "name": row.name}


async def verify_email(db: AsyncSession, token: str) -> dict:
    result = await db.execute(
        text("SELECT user_id, name, email FROM users WHERE verification_token = :token AND email_verified = FALSE"),
        {"token": token},
    )
    row = result.fetchone()
    if not row:
        raise ValueError("Invalid or already used verification link")
    await db.execute(
        text("UPDATE users SET email_verified = TRUE, verification_token = NULL WHERE user_id = :uid"),
        {"uid": row.user_id},
    )
    await db.commit()
    jwt_token = create_token(row.user_id)
    return {"access_token": jwt_token, "token_type": "bearer", "user_id": row.user_id, "name": row.name}


# ── me (get + update) ─────────────────────────────────────────────────────────

async def get_me(db: AsyncSession, user_id: int) -> dict:
    result = await db.execute(
        text("""
            SELECT u.user_id, u.name, u.email,
                   p.goal, p.gym_days_week, p.primary_sports,
                   p.garmin_email, p.garmin_password
            FROM users u
            LEFT JOIN user_profile p USING (user_id)
            WHERE u.user_id = :uid
        """),
        {"uid": user_id},
    )
    row = result.fetchone()
    if not row:
        raise ValueError("User not found")
    return {
        "user_id":         row.user_id,
        "name":            row.name,
        "email":           row.email,
        "goal":            row.goal,
        "gym_days_week":   row.gym_days_week,
        "primary_sports":  row.primary_sports or {},
        "garmin_email":    row.garmin_email,
        "garmin_password": row.garmin_password,
    }


async def delete_user(db: AsyncSession, user_id: int) -> None:
    await db.execute(text("DELETE FROM users WHERE user_id = :uid"), {"uid": user_id})
    await db.commit()


async def update_me(
    db: AsyncSession,
    user_id: int,
    name: str | None,
    goal: str | None,
    gym_days_week: int | None,
    primary_sports: dict | None,
    garmin_email: str | None,
    garmin_password: str | None,
) -> dict:
    import json
    if name is not None:
        await db.execute(
            text("UPDATE users SET name = :name WHERE user_id = :uid"),
            {"name": name, "uid": user_id},
        )

    # Scalar profile fields (skip None, but allow empty string to clear values)
    scalar_updates = {k: v for k, v in [
        ("goal", goal),
        ("gym_days_week", gym_days_week),
        ("garmin_email", garmin_email),
        ("garmin_password", garmin_password),
    ] if v is not None}

    if scalar_updates:
        set_clause = ", ".join(f"{k} = :{k}" for k in scalar_updates)
        scalar_updates["uid"] = user_id
        await db.execute(
            text(f"UPDATE user_profile SET {set_clause} WHERE user_id = :uid"),
            scalar_updates,
        )

    # JSONB field handled separately with explicit cast (required by asyncpg)
    if primary_sports is not None:
        await db.execute(
            text("UPDATE user_profile SET primary_sports = CAST(:v AS jsonb) WHERE user_id = :uid"),
            {"v": json.dumps(primary_sports), "uid": user_id},
        )

    await db.commit()
    return await get_me(db, user_id)
