import pytest
from photo_backup.time_utils import parse_interval, format_duration

class TestTimeUtilities:
    """Test cases for parse_interval and format_duration functions."""

    @pytest.mark.unit
    @pytest.mark.parametrize("interval_str,expected", [
        ("1h", 3600),
        ("2h30m", 9000),
        ("45m", 2700),
        ("10s", 10),
        ("1d", 86400),
        ("1d2h3m4s", 93784),
        ("5m30s", 330),
        ("2d12h", 216000),
        ("1h0m0s0d", 3600),
    ])
    def test_parse_interval_valid(self, interval_str, expected):
        assert parse_interval(interval_str) == expected

    @pytest.mark.unit
    @pytest.mark.parametrize("interval_str", ["", None, "abc", "0h", "1x", "1", "h"])
    def test_parse_interval_invalid(self, interval_str):
        with pytest.raises(ValueError):
            parse_interval(interval_str)

    @pytest.mark.unit
    @pytest.mark.parametrize("seconds,expected", [
        (0, "0s"),
        (59, "59s"),
        (60, "1m"),
        (61, "1m 1s"),
        (3600, "1h"),
        (3661, "1h 1m 1s"),
        (86400, "1d"),
        (90061, "1d 1h 1m 1s"),
        (172800, "2d"),
        (0.0, "0s"),
    ])
    def test_format_duration(self, seconds, expected):
        assert format_duration(seconds) == expected

    @pytest.mark.unit
    @pytest.mark.parametrize("seconds", [-1, None, "abc", [], {}])
    def test_format_duration_invalid(self, seconds):
        assert format_duration(seconds) == "0s"