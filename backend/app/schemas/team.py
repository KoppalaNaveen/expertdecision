from pydantic import BaseModel
from typing import Optional, List, Any, Union


class TeamMemberResponse(BaseModel):
    id: int
    employee_id: Optional[str] = None
    full_name: str
    role_name: Optional[str] = None
    designation: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True


class TeamBase(BaseModel):
    team_name: str
    description: Optional[str] = None


class TeamCreate(TeamBase):
    employee_ids: Optional[List[Union[int, str]]] = []


class TeamUpdate(TeamBase):
    employee_ids: Optional[List[Union[int, str]]] = None


class TeamResponse(TeamBase):
    id: int
    employee_count: int = 0
    employees: List[TeamMemberResponse] = []

    class Config:
        from_attributes = True


class UserTeamResponse(BaseModel):
    user_id: int
    employee_id: Optional[str] = None
    full_name: str
    team_id: Optional[int] = None
    team_name: str = "Not Assigned"
    description: Optional[str] = ""
    employee_count: int = 0
    employees: List[TeamMemberResponse] = []

    class Config:
        from_attributes = True
