"""Fix review_admin permissions to include 'assign'"""

from sqlalchemy import create_engine, text

from src.core.config import settings


db_url = f"mysql+pymysql://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
engine = create_engine(db_url)

with engine.connect() as conn:
    # Update review_admin role to include 'assign' permission
    conn.execute(
        text("""
        UPDATE role 
        SET permissions = '{"reviews": ["read", "create", "update", "delete", "assign"], "scores": ["read", "create", "update", "delete"], "projects": ["read", "manage"], "repositories": ["read", "manage"], "users": ["read"], "roles": ["read", "manage"]}',
        updated_at = NOW()
        WHERE name = 'review_admin'
    """)
    )
    conn.commit()
    print("✅ Updated review_admin permissions to include assign")

    # Verify
    result = conn.execute(text('SELECT name, permissions FROM role WHERE name = "review_admin"'))
    row = result.fetchone()
    print(f"\nRole: {row[0]}")
    print(f"Permissions: {row[1]}")
