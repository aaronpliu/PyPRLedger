-- Initialize database for Pull Request Code Review System

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS code_review CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE code_review;

-- Note: Tables will be created by Alembic migrations
-- Run migrations after database initialization:
-- alembic upgrade head
