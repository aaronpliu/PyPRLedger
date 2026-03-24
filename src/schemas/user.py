from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """Base user schema with common attributes"""

    user_id: int = Field(
        ..., gt=0, description="Unique user business identifier (e.g., GitHub user ID)"
    )
    username: str = Field(..., min_length=3, max_length=64, description="Username")
    display_name: str = Field(..., min_length=1, max_length=128, description="Display name")
    email_address: EmailStr = Field(..., description="User's email address")

    @field_validator("username")
    def username_alphanumeric(cls, v):
        """Validate username contains only alphanumeric characters and underscores"""
        if not all(c.isalnum() or c == "_" for c in v):
            raise ValueError("Username must contain only alphanumeric characters and underscores")
        return v.lower()  # Store lowercase


class UserCreate(UserBase):
    """Schema for creating a new user"""

    password: str | None = Field(None, min_length=8, max_length=128, description="User's password")
    is_reviewer: bool = Field(default=False, description="Whether the user is a reviewer")

    @field_validator("password")
    def password_strength(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserUpdate(BaseModel):
    """Schema for updating an existing user"""

    display_name: str | None = Field(None, min_length=1, max_length=128)
    email_address: EmailStr | None = None
    active: bool | None = None
    is_reviewer: bool | None = None


class UserResponse(UserBase):
    """Schema for user response"""

    id: int = Field(..., description="User ID")
    active: bool = Field(..., description="User active status")
    is_reviewer: bool = Field(..., description="Reviewer status")
    created_date: datetime = Field(..., description="User creation timestamp")
    updated_date: datetime = Field(..., description="User last update timestamp")

    class Config:
        """Pydantic configuration"""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "username": "john_doe",
                "display_name": "John Doe",
                "email_address": "john@example.com",
                "active": True,
                "is_reviewer": True,
                "created_date": "2023-01-01T00:00:00",
                "updated_date": "2023-01-01T00:00:00",
            }
        }


class UserInDB(UserResponse):
    """Schema representing user in the database (includes password hash)"""

    hashed_password: str = Field(..., description="Hashed password")

    class Config:
        """Pydantic configuration"""

        from_attributes = True


class UserLogin(BaseModel):
    """Schema for user login"""

    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class UserListResponse(BaseModel):
    """Schema for paginated user list response"""

    items: list[UserResponse] = Field(default_factory=list, description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(default=1, ge=1, description="Current page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Number of items per page")

    class Config:
        """Pydantic configuration"""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "items": [
                    {
                        "id": 1,
                        "username": "john_doe",
                        "display_name": "John Doe",
                        "email_address": "john@example.com",
                        "active": True,
                        "is_reviewer": True,
                        "created_date": "2023-01-01T00:00:00",
                        "updated_date": "2023-01-01T00:00:00",
                    }
                ],
                "total": 1,
                "page": 1,
                "page_size": 20,
            }
        }


class UserStats(BaseModel):
    """Schema for user statistics"""

    total_users: int = Field(..., description="Total number of users")
    active_users: int = Field(..., description="Number of active users")
    total_reviewers: int = Field(..., description="Number of reviewers")
    active_reviewers: int = Field(..., description="Number of active reviewers")

    class Config:
        """Pydantic configuration"""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "total_users": 100,
                "active_users": 95,
                "total_reviewers": 30,
                "active_reviewers": 28,
            }
        }
