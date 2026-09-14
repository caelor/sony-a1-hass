"""Encoding/decoding strategies for device-specific data formats.

CD players typically use BCD (Binary Coded Decimal) encoding for numeric values,
while MD players use raw hex values. This module provides codec strategies to
handle these differences transparently.
"""

from abc import ABC, abstractmethod


class Codec(ABC):
    """Abstract base class for encoding/decoding strategies."""

    @abstractmethod
    def decode_byte(self, value: int) -> int:
        """Decode a single byte value."""

    @abstractmethod
    def encode_byte(self, value: int) -> int:
        """Encode a single byte value."""


class BCDCodec(Codec):
    """BCD (Binary Coded Decimal) codec for CD players.

    BCD encoding: upper nibble * 10 + lower nibble
    Example: 0x45 → 4*10 + 5 = 45
    """

    def decode_byte(self, value: int) -> int:
        """Decode a BCD-encoded byte to its decimal value."""
        return ((value >> 4) & 0x0F) * 10 + (value & 0x0F)

    def encode_byte(self, value: int) -> int:
        """Encode a decimal value to BCD format."""
        tens = value // 10
        ones = value % 10
        return (tens << 4) | ones


class HexCodec(Codec):
    """Raw hex codec for MD players.

    Values are used as-is without conversion.
    """

    def decode_byte(self, value: int) -> int:
        """Return the value unchanged."""
        return value

    def encode_byte(self, value: int) -> int:
        """Return the value unchanged."""
        return value
