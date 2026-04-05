import hashlib
import json
import logging
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import (
    InvalidCredentialsException,
    UserAlreadyExistsException,
    UserNotFoundException,
)
from src.models.user import User
from src.schemas.user import (
    UserCreate,
    UserResponse,
    UserStats,
    UserUpdate,
)
from src.utils.metrics import MetricsCollector
from src.utils.redis import get_redis_client


logger = logging.getLogger(__name__)


class UserService:
    """Service for managing users"""

    def __init__(self, metrics_collector: MetricsCollector | None = None):
        """Initialize the user service"""
        self.redis_client = get_redis_client()
        self.metrics = metrics_collector or MetricsCollector()

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        pwd_bytes = password.encode("utf-8")
        salt = settings.SECRET_KEY.encode("utf-8")
        hash_obj = hashlib.sha256(pwd_bytes + salt)
        return hash_obj.hexdigest()

    def _get_cache_key(self, user_id: int) -> str:
        """Generate cache key for a user"""
        return f"user:{user_id}"

    def _get_username_cache_key(self, username: str) -> str:
        """Generate cache key for a username"""
        return f"user:username:{username}"

    def _get_email_cache_key(self, email: str) -> str:
        """Generate cache key for an email"""
        return f"user:email:{email}"

    def _get_list_cache_key(self, filters: dict[str, Any], page: int, page_size: int) -> str:
        """Generate cache key for user list"""
        filter_str = ":".join(f"{k}={v}" for k, v in sorted(filters.items()) if v is not None)
        return f"users:list:{filter_str}:{page}:{page_size}"

    async def _get_user_from_cache(self, user_id: int) -> dict[str, Any] | None:
        """Try to get user from cache"""
        try:
            cached = await self.redis_client.get(self._get_cache_key(user_id))
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Failed to get user from cache: {str(e)}")
        return None

    async def _set_user_in_cache(self, user_id: int, user_data: dict[str, Any]) -> None:
        """Store user in cache"""
        try:
            await self.redis_client.setex(
                self._get_cache_key(user_id), settings.CACHE_TTL_USERS, json.dumps(user_data)
            )
        except Exception as e:
            logger.warning(f"Failed to set user in cache: {str(e)}")

    async def _invalidate_user_cache(self, user_id: int, username: str, email: str) -> None:
        """Invalidate user cache entries"""
        try:
            await self.redis_client.delete(self._get_cache_key(user_id))
            await self.redis_client.delete(self._get_username_cache_key(username))
            await self.redis_client.delete(self._get_email_cache_key(email))
        except Exception as e:
            logger.warning(f"Failed to invalidate user cache: {str(e)}")

    async def _invalidate_list_cache(self) -> None:
        """Invalidate all user list cache entries"""
        try:
            keys = await self.redis_client.keys("users:list:*")
            if keys:
                await self.redis_client.delete(*keys)
        except Exception as e:
            logger.warning(f"Failed to invalidate list cache: {str(e)}")

    async def create_user(self, user_data: UserCreate, db: AsyncSession) -> UserResponse:
        """
        Create a new user

        Args:
            user_data: The user data to create
            db: Database session

        Returns:
            UserResponse: The created user

        Raises:
            UserAlreadyExistsException: If a user with the same username or email already exists
        """
        # Check if username already exists
        existing_username = await db.execute(
            select(User).where(User.username == user_data.username)
        )
        if existing_username.scalar_one_or_none():
            raise UserAlreadyExistsException(username=user_data.username)

        # Check if email already exists
        existing_email = await db.execute(
            select(User).where(User.email_address == user_data.email_address)
        )
        if existing_email.scalar_one_or_none():
            raise UserAlreadyExistsException(email=user_data.email_address)

        # Create new user
        # hashed_password = self.hash_password(user_data.password)
        new_user = User(
            username=user_data.username,
            display_name=user_data.display_name,
            email_address=user_data.email_address,
            active=True,
            is_reviewer=user_data.is_reviewer,
        )

        db.add(new_user)
        await db.flush()
        await db.refresh(new_user)
        await db.commit()  # Commit the transaction to make data visible to other connections

        # Cache the new user
        user_dict = new_user.to_dict()
        await self._set_user_in_cache(new_user.id, user_dict)

        # Invalidate list cache
        await self._invalidate_list_cache()

        # Update metrics
        self.metrics.increment_user_count()
        if user_data.is_reviewer:
            self.metrics.increment_reviewer_count()

        logger.info(f"Created new user: {new_user.username} (ID: {new_user.id})")
        return UserResponse(**new_user.to_dict())

    async def get_user_by_id(
        self, user_id: int, db: AsyncSession, use_cache: bool = True
    ) -> dict | None:
        """
        Get a user by ID

        Args:
            user_id: The user ID
            db: Database session
            use_cache: Whether to use cache

        Returns:
            Dict: The user as dictionary, or None if not found
        """
        # Try cache first
        if use_cache:
            cached = await self._get_user_from_cache(user_id)
            if cached:
                logger.debug(f"Retrieved user from cache: {user_id}")
                return cached

        # Query database
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user:
            # Cache the result
            user_dict = user.to_dict()
            await self._set_user_in_cache(user_id, user_dict)
            return user_dict

        return None

    async def get_user_by_username(
        self, username: str, db: AsyncSession, use_cache: bool = True
    ) -> dict | None:
        """
        Get a user by username

        Args:
            username: The username
            db: Database session
            use_cache: Whether to use cache

        Returns:
            Dict: The user as dictionary, or None if not found
        """
        # Try cache first
        if use_cache:
            try:
                cache_key = self._get_username_cache_key(username)
                user_id = await self.redis_client.get(cache_key)
                if user_id:
                    user = await self.get_user_by_id(int(user_id), db, use_cache)
                    return user
            except Exception as e:
                logger.warning(f"Failed to get username mapping from cache: {str(e)}")

        # Query database
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if user:
            user_dict = user.to_dict()
            if use_cache:
                try:
                    # Cache username to user_id mapping
                    cache_key = self._get_username_cache_key(username)
                    await self.redis_client.setex(cache_key, settings.CACHE_TTL_USERS, str(user.id))
                    # Cache the user
                    await self._set_user_in_cache(user.id, user_dict)
                except Exception as e:
                    logger.warning(f"Failed to set username mapping in cache: {str(e)}")
            return user_dict

        return None

    async def get_user_by_email(
        self, email: str, db: AsyncSession, use_cache: bool = True
    ) -> dict | None:
        """
        Get a user by email

        Args:
            email: The email address
            db: Database session
            use_cache: Whether to use cache

        Returns:
            Dict: The user as dictionary, or None if not found
        """
        # Try cache first
        if use_cache:
            try:
                cache_key = self._get_email_cache_key(email)
                user_id = await self.redis_client.get(cache_key)
                if user_id:
                    user = await self.get_user_by_id(int(user_id), db, use_cache)
                    return user
            except Exception as e:
                logger.warning(f"Failed to get email mapping from cache: {str(e)}")

        # Query database
        result = await db.execute(select(User).where(User.email_address == email))
        user = result.scalar_one_or_none()

        if user:
            user_dict = user.to_dict()
            if use_cache:
                try:
                    # Cache email to user_id mapping
                    cache_key = self._get_email_cache_key(email)
                    await self.redis_client.setex(cache_key, settings.CACHE_TTL_USERS, str(user.id))
                    # Cache the user
                    await self._set_user_in_cache(user.id, user_dict)
                except Exception as e:
                    logger.warning(f"Failed to set email mapping in cache: {str(e)}")
            return user_dict

        return None

    async def list_users(
        self,
        db: AsyncSession,
        active: bool | None = None,
        is_reviewer: bool | None = None,
        username: str | None = None,
        page: int = 1,
        page_size: int = 20,
        use_cache: bool = True,
    ) -> tuple[list[User], int]:
        """
        List users with filtering and pagination

        Args:
            active: Filter by active status
            is_reviewer: Filter by reviewer status
            username: Filter by username (partial match)
            page: Page number (1-indexed)
            page_size: Number of items per page
            db: Database session
            use_cache: Whether to use cache

        Returns:
            Tuple[List[User], int]: List of users and total count
        """
        # Build filter dictionary for cache key
        filter_dict = {"active": active, "is_reviewer": is_reviewer, "username": username}
        filter_dict = {k: v for k, v in filter_dict.items() if v is not None}

        # Try cache first for list results
        if use_cache:
            try:
                cache_key = self._get_list_cache_key(filter_dict, page, page_size)
                cached = await self.redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # Return users as dicts from cache (not ORM objects)
                    logger.debug("Retrieved user list from cache")
                    return data["users"], data["total"]
            except Exception as e:
                logger.warning(f"Failed to get user list from cache: {str(e)}")

        # Build query conditions
        conditions = []
        if active is not None:
            conditions.append(User.active == active)
        if is_reviewer is not None:
            conditions.append(User.is_reviewer == is_reviewer)
        if username:
            conditions.append(User.username.like(f"%{username}%"))

        # Get total count
        count_query = select(func.count()).select_from(User)
        if conditions:
            count_query = count_query.where(and_(*conditions))

        count_result = await db.execute(count_query)
        total = count_result.scalar()

        # Get users
        query = (
            select(User)
            .order_by(desc(User.created_date))
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        if conditions:
            query = query.where(and_(*conditions))

        result = await db.execute(query)
        users = result.scalars().all()

        # Cache the result
        if use_cache and users:
            try:
                cache_key = self._get_list_cache_key(filter_dict, page, page_size)
                cache_data = {"users": [u.to_dict() for u in users], "total": total}
                await self.redis_client.setex(
                    cache_key, settings.CACHE_TTL_USERS, json.dumps(cache_data)
                )
            except Exception as e:
                logger.warning(f"Failed to cache user list: {str(e)}")

        return list(users), total

    async def update_user(self, user_id: int, update_data: UserUpdate, db: AsyncSession) -> dict:
        """
        Update a user

        Args:
            user_id: The user ID
            update_data: The update data
            db: Database session

        Returns:
            Dict: The updated user as dictionary

        Raises:
            UserNotFoundException: If the user doesn't exist
        """
        # Get ORM object for update
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundException(user_id=user_id)

        # Check if email is being updated and already exists
        if update_data.email_address and update_data.email_address != user.email_address:
            existing_email = await db.execute(
                select(User).where(
                    and_(User.email_address == update_data.email_address, User.id != user_id)
                )
            )
            if existing_email.scalar_one_or_none():
                raise UserAlreadyExistsException(email=update_data.email_address)

        # Update user
        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)

        # Invalidate cache
        await self._invalidate_user_cache(user_id, user.username, user.email_address)
        await self._invalidate_list_cache()

        # Update metrics
        if update_data.is_reviewer:
            if update_data.is_reviewer != user.is_reviewer:
                if update_data.is_reviewer:
                    self.metrics.increment_reviewer_count()
                else:
                    self.metrics.decrement_reviewer_count()

        logger.info(f"Updated user: {user.username} (ID: {user_id})")
        return user.to_dict()

    async def delete_user(self, user_id: int, db: AsyncSession) -> bool:
        """
        Delete a user

        Args:
            user_id: The user ID
            db: Database session

        Returns:
            bool: True if deleted, False if not found
        """
        user = await self.get_user_by_id(user_id, db, use_cache=False)
        if not user:
            return False

        await db.delete(user)

        # Invalidate cache
        await self._invalidate_user_cache(user_id, user.username, user.email_address)
        await self._invalidate_list_cache()

        # Update metrics
        self.metrics.decrement_user_count()
        if user.is_reviewer:
            self.metrics.decrement_reviewer_count()

        logger.info(f"Deleted user: {user.username} (ID: {user_id})")
        return True

    async def validate_credentials(
        self, username: str, password: str, db: AsyncSession
    ) -> User | None:
        """
        Validate user credentials (simplified - checks if user exists and is active)

        Note: In a production system, you would integrate with an authentication service
        and validate the password properly.

        Args:
            username: The username
            password: The password to validate
            db: Database session

        Returns:
            User: The user if credentials are valid, None otherwise

        Raises:
            InvalidCredentialsException: If credentials are invalid
        """
        user = await self.get_user_by_username(username, db, use_cache=False)

        if not user or not user.active:
            raise InvalidCredentialsException()

        # TODO: Implement proper password validation with authentication service
        # For now, we assume password is validated externally

        logger.info(f"Validated credentials for user: {username}")
        return user

    async def get_user_statistics(self, db: AsyncSession, use_cache: bool = True) -> UserStats:
        """
        Get user statistics

        Args:
            db: Database session
            use_cache: Whether to use cache

        Returns:
            UserStats: User statistics
        """
        # Try cache first
        cache_key = "stats:users"
        if use_cache:
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    return UserStats(**json.loads(cached))
            except Exception as e:
                logger.warning(f"Failed to get user stats from cache: {str(e)}")

        # Get total users
        total_query = select(func.count()).select_from(User)
        total_result = await db.execute(total_query)
        total_users = total_result.scalar()

        # Get active users
        active_query = select(func.count()).select_from(User).where(User.active == True)
        active_result = await db.execute(active_query)
        active_users = active_result.scalar()

        # Get total reviewers
        reviewer_query = select(func.count()).select_from(User).where(User.is_reviewer == True)
        reviewer_result = await db.execute(reviewer_query)
        total_reviewers = reviewer_result.scalar()

        # Get active reviewers
        active_reviewer_query = (
            select(func.count())
            .select_from(User)
            .where(and_(User.is_reviewer == True, User.active == True))
        )
        active_reviewer_result = await db.execute(active_reviewer_query)
        active_reviewers = active_reviewer_result.scalar()

        # Create statistics object
        stats = UserStats(
            total_users=total_users,
            active_users=active_users,
            total_reviewers=total_reviewers,
            active_reviewers=active_reviewers,
        )

        # Cache the result
        if use_cache:
            try:
                await self.redis_client.setex(
                    cache_key, settings.CACHE_TTL_STATS, json.dumps(stats.model_dump())
                )
            except Exception as e:
                logger.warning(f"Failed to cache user stats: {str(e)}")

        return stats

    async def get_active_reviewers(self, db: AsyncSession, limit: int = 100) -> list[dict]:
        """
        Get active reviewers

        Args:
            db: Database session
            limit: Maximum number of reviewers to return

        Returns:
            List[Dict]: List of active reviewers as dictionaries
        """
        result = await db.execute(
            select(User)
            .where(and_(User.is_reviewer == True, User.active == True))
            .order_by(User.created_date)
            .limit(limit)
        )
        users = result.scalars().all()
        return [user.to_dict() for user in users]

    async def toggle_reviewer_status(self, user_id: int, db: AsyncSession) -> dict:
        """
        Toggle reviewer status for a user

        Args:
            user_id: The user ID
            db: Database session

        Returns:
            Dict: The updated user as dictionary

        Raises:
            UserNotFoundException: If the user doesn't exist
        """
        # Get ORM object for update
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundException(user_id=user_id)

        # Toggle reviewer status
        user.is_reviewer = not user.is_reviewer

        # Invalidate cache
        await self._invalidate_user_cache(user_id, user.username, user.email_address)
        await self._invalidate_list_cache()

        # Update metrics
        if user.is_reviewer:
            self.metrics.increment_reviewer_count()
        else:
            self.metrics.decrement_reviewer_count()

        logger.info(
            f"Toggled reviewer status for user: {user.username} (ID: {user_id}) to {user.is_reviewer}"
        )
        return user.to_dict()

    async def activate_user(self, user_id: int, db: AsyncSession) -> dict:
        """
        Activate a user

        Args:
            user_id: The user ID
            db: Database session

        Returns:
            Dict: The updated user as dictionary

        Raises:
            UserNotFoundException: If the user doesn't exist
        """
        # Get ORM object for update
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundException(user_id=user_id)

        if not user.active:
            user.active = True
            # Invalidate cache
            await self._invalidate_user_cache(user_id, user.username, user.email_address)
            await self._invalidate_list_cache()

            logger.info(f"Activated user: {user.username} (ID: {user_id})")

        return user.to_dict()

    async def deactivate_user(self, user_id: int, db: AsyncSession) -> dict:
        """
        Deactivate a user

        Args:
            user_id: The user ID
            db: Database session

        Returns:
            Dict: The updated user as dictionary

        Raises:
            UserNotFoundException: If the user doesn't exist
        """
        # Get ORM object for update
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFoundException(user_id=user_id)

        if user.active:
            user.active = False
            # Invalidate cache
            await self._invalidate_user_cache(user_id, user.username, user.email_address)
            await self._invalidate_list_cache()

            logger.info(f"Deactivated user: {user.username} (ID: {user_id})")

        return user.to_dict()
