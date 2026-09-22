"""Formatting helpers with no dependencies of their own."""

from __future__ import annotations

MB = 1_000_000
KB = 1_000


def human_size(size_bytes: int) -> str:
    """Byte count as a short decimal string. Decimal, not binary: 37.8 MB, not 36 MiB."""
    if size_bytes >= MB:
        return f"{size_bytes / MB:.1f} MB"
    if size_bytes >= KB:
        return f"{size_bytes / KB:.1f} kB"
    return f"{size_bytes} B"
