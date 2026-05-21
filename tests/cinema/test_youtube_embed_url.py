"""Unit tests for youtube_embed_url helper (US-13 / FR-03)."""

from apps.cinema.utils import youtube_embed_url

EMBED = "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"


class TestYouTubeEmbedUrl:
    def test_none_returns_none(self):
        assert youtube_embed_url(None) is None

    def test_empty_string_returns_none(self):
        assert youtube_embed_url("") is None

    def test_non_youtube_url_returns_none(self):
        assert youtube_embed_url("https://example.com/clip.mp4") is None

    def test_watch_url(self):
        assert youtube_embed_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == EMBED

    def test_short_youtu_be_url(self):
        assert youtube_embed_url("https://youtu.be/dQw4w9WgXcQ") == EMBED

    def test_already_embed_url(self):
        assert youtube_embed_url("https://www.youtube.com/embed/dQw4w9WgXcQ") == EMBED

    def test_mobile_youtube_url(self):
        assert youtube_embed_url("https://m.youtube.com/watch?v=dQw4w9WgXcQ") == EMBED

    def test_watch_url_with_extra_params(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s&feature=share"
        assert youtube_embed_url(url) == EMBED

    def test_watch_url_missing_v_param_returns_none(self):
        assert youtube_embed_url("https://www.youtube.com/watch") is None

    def test_invalid_video_id_length_returns_none(self):
        # YouTube IDs are exactly 11 chars; "tooshort" is 8.
        assert youtube_embed_url("https://www.youtube.com/watch?v=tooshort") is None
