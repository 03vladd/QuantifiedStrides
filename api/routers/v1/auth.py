import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id, get_db
from api.schemas.auth import (
    LoginSchema, RegisterSchema, TokenSchema,
    UpdateProfileSchema, UserProfileSchema,
)
from api.services import auth as auth_svc
from api.services.email import send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
async def register(body: RegisterSchema, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_svc.register(
            db,
            name=body.name,
            email=body.email,
            password=body.password,
            goal=body.goal,
            gym_days_week=body.gym_days_week,
            primary_sports=body.primary_sports,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Send verification email in background (non-blocking)
    asyncio.get_event_loop().run_in_executor(
        None,
        send_verification_email,
        user["email"],
        user["name"],
        user["verification_token"],
    )

    return {"message": "Account created. Check your email to verify your account."}


@router.post("/login", response_model=TokenSchema)
async def login(body: LoginSchema, db: AsyncSession = Depends(get_db)):
    try:
        result = await auth_svc.login(db, email=body.email, password=body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return TokenSchema(**result)


@router.get("/verify")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    try:
        result = await auth_svc.verify_email(db, token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return TokenSchema(**result)


@router.get("/me", response_model=UserProfileSchema)
async def get_me(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await auth_svc.get_me(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/me", status_code=204)
async def delete_me(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await auth_svc.delete_user(db, user_id)


@router.put("/me", response_model=UserProfileSchema)
async def update_me(
    body: UpdateProfileSchema,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await auth_svc.update_me(
        db, user_id,
        name=body.name,
        goal=body.goal,
        gym_days_week=body.gym_days_week,
        primary_sports=body.primary_sports,
        garmin_email=body.garmin_email,
        garmin_password=body.garmin_password,
    )
