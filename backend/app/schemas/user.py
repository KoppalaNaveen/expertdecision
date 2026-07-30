from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# -----------------------------
# User Registration Workflow Schemas
# -----------------------------
class RegisterStep1(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role_id: int
    team_id: Optional[int] = 1
    designation: Optional[str] = None
    phone: Optional[str] = None

class CheckEmployeeIDRequest(BaseModel):
    role_id: int
    employee_id: str

class SaveEmployeeIDRequest(BaseModel):
    email: EmailStr
    role_id: int
    employee_id: str
    full_name: str
    password: str
    team_id: Optional[int] = 1
    designation: Optional[str] = None
    phone: Optional[str] = None

class AdminApprovalAction(BaseModel):
    user_id: int
    action: str = Field(..., pattern="^(approve|reject)$")
    actor_name: Optional[str] = "Administrator"

class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role_id: int
    team_id: int
    employee_id: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None
    verification_code: str = Field(..., min_length=6, max_length=6)

class AdminUserCreate(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role_id: int
    team_id: Optional[int] = 1
    employee_id: Optional[str] = None
    designation: Optional[str] = None
    phone: Optional[str] = None

# -----------------------------
# Code Verification
# -----------------------------
class SendCodeRequest(BaseModel):
    email: EmailStr
    purpose: str = Field(..., pattern="^(register|reset_password)$")
    is_resend: bool = False

class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    purpose: str = Field(..., pattern="^(register|reset_password)$")

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=6)

# -----------------------------
# User Login
# -----------------------------
class UserLogin(BaseModel):
    employee_id: str
    password: str


# -----------------------------
# JWT Token Response
# -----------------------------
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    role_name: Optional[str] = None
    full_name: Optional[str] = None

# -----------------------------
# User Response
# -----------------------------
class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    employee_id: Optional[str] = None
    role_id: int
    team_id: Optional[int] = 1
    designation: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool = True
    email_verified: Optional[bool] = False
    approved: Optional[bool] = False
    status: Optional[str] = "Pending Approval"
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[str] = None
    created_at: Optional[str] = None
    role_name: Optional[str] = None

    model_config = {
        "from_attributes": True
    }