"""Check bob_reviewer's permissions"""

import asyncio

from sqlalchemy import select

from src.core.database import get_db_context, init_db
from src.models.auth_user import AuthUser
from src.models.role import Role
from src.models.user import User


async def check_permissions():
    await init_db()

    async with get_db_context() as db:
        # Find bob_reviewer
        stmt = select(User).where(User.username == "bob_reviewer")
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            print("❌ User 'bob_reviewer' not found")
            return

        print(f"✅ Found user: {user.username} (ID: {user.id})")
        print(f"   is_reviewer: {user.is_reviewer}")

        # Get auth_user
        stmt = select(AuthUser).where(AuthUser.user_id == user.id)
        result = await db.execute(stmt)
        auth_user = result.scalar_one_or_none()

        if not auth_user:
            print("❌ No auth_user linked to this user")
            return

        print(f"✅ Auth user ID: {auth_user.id}")

        # Get roles
        from src.models.rbac import UserRoleAssignment

        stmt = select(UserRoleAssignment).where(UserRoleAssignment.auth_user_id == auth_user.id)
        result = await db.execute(stmt)
        assignments = result.scalars().all()

        if not assignments:
            print("❌ No role assignments found")
            return

        print(f"\n📋 Role Assignments ({len(assignments)}):")
        for assignment in assignments:
            # Get role details
            stmt = select(Role).where(Role.id == assignment.role_id)
            result = await db.execute(stmt)
            role = result.scalar_one_or_none()

            if role:
                print(f"   - Role: {role.name} (ID: {assignment.role_id})")
                print(f"     Permissions: {role.permissions}")

                # Check if has assign permission
                if "reviews" in role.permissions and "assign" in role.permissions["reviews"]:
                    print("     ✅ Has 'assign' permission on reviews")
                else:
                    print("     ❌ Missing 'assign' permission on reviews")
                    print(
                        f"     Available review permissions: {role.permissions.get('reviews', [])}"
                    )


if __name__ == "__main__":
    asyncio.run(check_permissions())
