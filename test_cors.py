#!/usr/bin/env python3
"""Test CORS configuration parsing"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field
from typing import List


class TestSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    BACKEND_CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:8000"
    )
    
    @computed_field
    @property
    def BACKEND_CORS_ORIGINS_LIST(self) -> List[str]:
        return [x.strip() for x in self.BACKEND_CORS_ORIGINS.split(',')]


# Test with .env file
print("Testing with .env file...")
try:
    s = TestSettings()
    print(f"✓ Success! CORS origins: {s.BACKEND_CORS_ORIGINS_LIST}")
    print(f"  Type: {type(s.BACKEND_CORS_ORIGINS_LIST)}")
    print(f"  Raw value: {s.BACKEND_CORS_ORIGINS}")
except Exception as e:
    print(f"✗ Error: {e}")
