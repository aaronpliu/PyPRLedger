from __future__ import annotations

import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image

from src.core.config import settings


class AvatarService:
    """Service for handling user avatar upload and deletion"""

    # Avatar dimensions (square)
    AVATAR_SIZE = 400  # pixels
    THUMBNAIL_SIZE = 80  # pixels for smaller displays

    def __init__(self) -> None:
        self.upload_dir = Path(settings.AVATAR_UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def upload_avatar(self, user_id: int, file: UploadFile) -> str:
        """Upload, process, resize, and save user avatar. Original file is discarded."""
        # Validate file type
        if file.content_type not in settings.ALLOWED_AVATAR_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(sorted(settings.ALLOWED_AVATAR_TYPES))}",
            )

        # Read file content to validate size
        file_content = await file.read()
        if len(file_content) > settings.MAX_AVATAR_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {settings.MAX_AVATAR_SIZE // (1024 * 1024)}MB",
            )

        try:
            # Open image with Pillow
            image = Image.open(io.BytesIO(file_content))

            # Convert to RGB if necessary (for PNG with transparency or GIF)
            if image.mode in ("RGBA", "P", "LA"):
                # Create white background for transparent images
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(
                    image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None
                )
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")

            # Resize image maintaining aspect ratio, then crop to square
            image = self._resize_and_crop(image, self.AVATAR_SIZE)

            # Determine output format and extension based on original file type
            content_type = file.content_type or "image/jpeg"
            if content_type == "image/png":
                save_format = "PNG"
                file_extension = "png"
            elif content_type in ("image/webp", "image/gif"):
                # Convert WebP and GIF to PNG to preserve quality
                save_format = "PNG"
                file_extension = "png"
            else:  # image/jpeg or image/jpg
                save_format = "JPEG"
                file_extension = "jpg"

            # Generate unique filename with preserved extension
            unique_filename = f"{user_id}_{uuid.uuid4().hex}.{file_extension}"
            file_path = self.upload_dir / unique_filename

            # Save processed avatar with appropriate format
            if save_format == "JPEG":
                image.save(file_path, "JPEG", quality=85, optimize=True)
            else:  # PNG
                image.save(file_path, "PNG", optimize=True)

            # Also create a thumbnail version (80x80px)
            thumbnail = self._resize_and_crop(image, self.THUMBNAIL_SIZE)
            thumbnail_path = self.upload_dir / f"thumb_{unique_filename}"
            if save_format == "JPEG":
                thumbnail.save(thumbnail_path, "JPEG", quality=75, optimize=True)
            else:  # PNG
                thumbnail.save(thumbnail_path, "PNG", optimize=True)

            # Note: Original uploaded file is NOT saved - only processed versions
            # The file_content in memory is discarded after processing

            # Return URL path (main avatar)
            return f"{settings.AVATAR_BASE_URL}/{unique_filename}"

        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image file: {str(e)}",
            )

    def _resize_and_crop(self, image: Image.Image, size: int) -> Image.Image:
        """Resize image and crop to square"""
        # Get original dimensions
        width, height = image.size

        # Calculate cropping box to make it square
        min_dim = min(width, height)
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim

        # Crop to square
        image = image.crop((left, top, right, bottom))

        # Resize to target size
        image = image.resize((size, size), Image.Resampling.LANCZOS)

        return image

    def delete_avatar(self, avatar_url: str) -> None:
        """Delete old avatar file and thumbnail"""
        if not avatar_url:
            return

        filename = avatar_url.split("/")[-1]
        file_path = self.upload_dir / filename
        thumbnail_path = self.upload_dir / f"thumb_{filename}"

        # Delete main avatar
        if file_path.exists():
            file_path.unlink()

        # Delete thumbnail
        if thumbnail_path.exists():
            thumbnail_path.unlink()
