from pydantic import BaseModel, EmailStr, Field


class RegisterSchema(BaseModel):
    name:           str
    email:          EmailStr
    password:       str = Field(min_length=6)
    goal:           str = Field(default="athlete")
    gym_days_week:  int = Field(default=3, ge=2, le=6)
    primary_sports: dict[str, int] = Field(default_factory=dict)


class LoginSchema(BaseModel):
    email:    EmailStr
    password: str


class TokenSchema(BaseModel):
    access_token: str
    token_type:   str
    user_id:      int
    name:         str


class UserProfileSchema(BaseModel):
    user_id:          int
    name:             str
    email:            str
    goal:             str | None
    gym_days_week:    int | None
    primary_sports:   dict[str, int]
    garmin_email:     str | None = None
    garmin_password:  str | None = None


class UpdateProfileSchema(BaseModel):
    name:             str | None = None
    goal:             str | None = None
    gym_days_week:    int | None = Field(default=None, ge=2, le=6)
    primary_sports:   dict[str, int] | None = None
    garmin_email:     str | None = None
    garmin_password:  str | None = None
