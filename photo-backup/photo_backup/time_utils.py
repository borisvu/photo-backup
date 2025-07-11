import re

def parse_interval(interval_str):
    """Parse a time interval string (e.g., '4h', '30m', '2d', '1h30m') to seconds.
    Supports days (d), hours (h), minutes (m), seconds (s).
    Args:
        interval_str (str): Interval string
    Returns:
        int: Total seconds
    Raises:
        ValueError: If the format is invalid
    """
    if not isinstance(interval_str, str) or not interval_str.strip():
        raise ValueError("Interval string must be a non-empty string")
    pattern = re.compile(r"(?P<value>\d+)(?P<unit>[dhms])", re.IGNORECASE)
    total_seconds = 0
    for match in pattern.finditer(interval_str):
        value = int(match.group("value"))
        unit = match.group("unit").lower()
        if unit == "d":
            total_seconds += value * 86400
        elif unit == "h":
            total_seconds += value * 3600
        elif unit == "m":
            total_seconds += value * 60
        elif unit == "s":
            total_seconds += value
        else:
            raise ValueError(f"Unknown time unit: {unit}")
    if total_seconds == 0:
        raise ValueError(f"Invalid interval string: {interval_str}")
    return total_seconds

def format_duration(seconds):
    """Format a duration in seconds to a human-readable string (e.g., '1h 23m 45s').
    Args:
        seconds (int): Number of seconds
    Returns:
        str: Formatted duration
    """
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "0s"
    seconds = int(seconds)
    parts = []
    days, seconds = divmod(seconds, 86400)
    if days:
        parts.append(f"{days}d")
    hours, seconds = divmod(seconds, 3600)
    if hours:
        parts.append(f"{hours}h")
    minutes, seconds = divmod(seconds, 60)
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)
