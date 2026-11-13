import pytest

from photo_backup.format_utils import format_bytes


class TestFormatBytes:
    """Test cases for format_bytes function."""

    @pytest.mark.parametrize(
        "bytes_value,expected",
        [
            (0, "0 B"),
            (1, "1 B"),
            (512, "512 B"),
            (1023, "1023 B"),
            (1024, "1.00 KB"),
            (1536, "1.50 KB"),
            (10240, "10.0 KB"),
            (102400, "100 KB"),
            (1048576, "1.00 MB"),
            (1073741824, "1.00 GB"),
            (1099511627776, "1.00 TB"),
            (1125899906842624, "1.00 PB"),
        ],
    )
    @pytest.mark.unit
    def test_format_bytes_standard_cases(self, bytes_value, expected):
        """Test format_bytes with standard byte values."""
        result = format_bytes(bytes_value)
        assert result == expected, f"format_bytes({bytes_value}) = {result}, expected {expected}"

    @pytest.mark.parametrize(
        "invalid_input,expected",
        [
            (-1, "0 B"),
            ("invalid", "0 B"),
            (None, "0 B"),
            ([], "0 B"),
            ({}, "0 B"),
        ],
    )
    @pytest.mark.unit
    def test_format_bytes_edge_cases(self, invalid_input, expected):
        """Test format_bytes with invalid inputs."""
        result = format_bytes(invalid_input)
        assert result == expected

    @pytest.mark.parametrize(
        "bytes_value,expected_precision",
        [
            (1500, 2),  # 1.46 KB - < 10, show 2 decimals
            (15000, 1),  # 14.6 KB - >= 10, show 1 decimal
            (150000, 0),  # 146 KB - >= 100, show 0 decimals
        ],
    )
    @pytest.mark.unit
    def test_format_bytes_precision(self, bytes_value, expected_precision):
        """Test format_bytes precision formatting."""
        result = format_bytes(bytes_value)
        if expected_precision == 0:
            assert "." not in result.split()[0]
        else:
            decimal_part = result.split()[0].split(".")[1]
            assert len(decimal_part) == expected_precision
