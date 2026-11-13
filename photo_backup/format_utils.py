def format_bytes(bytes_value: float | None) -> str:
    """Convert bytes to human-readable format.

    Args:
        bytes_value (int): Number of bytes to format

    Returns:
        str: Human-readable size (e.g., "1.5 GB", "256 MB", "1.2 KB")
    """
    if not isinstance(bytes_value, int | float) or bytes_value < 0:
        return "0 B"

    if bytes_value == 0:
        return "0 B"

    # Define size units
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    size = float(bytes_value)

    # Find the appropriate unit
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    # Format with appropriate precision
    if unit_index == 0:  # Bytes
        return f"{int(size)} {units[unit_index]}"
    elif size >= 100:
        return f"{size:.0f} {units[unit_index]}"
    elif size >= 10:
        return f"{size:.1f} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}"
