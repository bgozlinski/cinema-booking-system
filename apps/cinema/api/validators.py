from PIL import Image
from rest_framework import serializers

MAX_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image_upload(value):
    """Reject images over 5MB or outside JPEG/PNG/WebP. Size is checked first."""
    if value.size > MAX_IMAGE_SIZE:
        raise serializers.ValidationError("Image must be 5MB or smaller.")
    try:
        fmt = Image.open(value).format
    except Exception as exc:
        raise serializers.ValidationError("Upload a valid image.") from exc
    finally:
        value.seek(0)
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise serializers.ValidationError("Image must be JPEG, PNG, or WebP.")
