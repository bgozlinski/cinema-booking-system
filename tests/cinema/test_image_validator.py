from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import serializers

from apps.cinema.api.validators import validate_image_upload


def _image(fmt="PNG"):
    buf = BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format=fmt)
    buf.seek(0)
    return SimpleUploadedFile(f"x.{fmt.lower()}", buf.read(), content_type=f"image/{fmt.lower()}")


def test_valid_png_passes():
    validate_image_upload(_image("PNG"))  # no exception


def test_valid_webp_passes():
    validate_image_upload(_image("WEBP"))  # no exception


def test_gif_rejected():
    with pytest.raises(serializers.ValidationError):
        validate_image_upload(_image("GIF"))


def test_oversized_rejected():
    big = SimpleUploadedFile("big.png", b"x" * (5 * 1024 * 1024 + 1), content_type="image/png")
    with pytest.raises(serializers.ValidationError):
        validate_image_upload(big)
