import re
from urllib.parse import parse_qs, urlparse

_YOUTUBE_HOSTS = {"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"}
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def youtube_embed_url(url: str | None) -> str | None:
    """Return a privacy-respecting youtube-nocookie embed URL, or None if
    the input is missing/not a recognized YouTube URL.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.hostname not in _YOUTUBE_HOSTS:
        return None

    video_id = None
    if parsed.hostname == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]

    elif parsed.path == "/watch":
        v_param = parse_qs(parsed.query).get("v")
        video_id = v_param[0] if v_param else None

    elif parsed.path.startswith("/embed/"):
        parts = parsed.path.split("/")
        video_id = parts[2] if len(parts) > 2 else None

    if not video_id or not _VIDEO_ID_RE.match(video_id):
        return None
    return f"https://www.youtube-nocookie.com/embed/{video_id}"
