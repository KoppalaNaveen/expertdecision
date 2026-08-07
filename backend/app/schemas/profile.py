from pydantic import BaseModel, EmailStr
from typing import Optional


class ProfileResponse(BaseModel):
    id: int
    full_name: str
    email: str
    email_original: Optional[str] = None
    employee_id: Optional[str] = None
    phone: Optional[str] = None
    designation: Optional[str] = None
    role: Optional[str] = "User"
    team: Optional[str] = "General"
    is_own_profile: bool = False
    email_hash: Optional[str] = None

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    full_name: str
    phone: Optional[str] = None
    designation: Optional[str] = None