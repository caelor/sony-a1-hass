"""Title reassembler for chunked title data from Control-A1 bus messages.

Reassembles titles split across multiple messages: a 14-byte initial block
followed by zero or more 16-byte continuation blocks. Titles are null-padded,
so a zero byte within the character data indicates end of title.
"""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

_INITIAL_BLOCK_SIZE = 14
_CONTINUATION_BLOCK_SIZE = 16


class TitleReassembler:
    """Reassembles a title from chunked block data.

    Block 1 provides 14 bytes. Blocks 2+ each provide 16 bytes.
    A null byte (0x00) within the data signals end of title.
    """

    def __init__(self, initial_data: bytes) -> None:
        self._buffer: bytearray = bytearray(initial_data)
        self._expected_block: int = 2
        self._complete: bool = False
        self._check_for_null(initial_data)

    def _check_for_null(self, data: bytes) -> None:
        if b"\x00" in data:
            null_pos = data.index(0)
            self._buffer = bytearray(self._buffer[:len(self._buffer) - len(data) + null_pos])
            self._complete = True

    @property
    def is_complete(self) -> bool:
        return self._complete

    def get_title(self) -> str | None:
        if not self._complete:
            return None
        return self._buffer.decode("ascii", errors="replace")

    def add_block(self, block_num: int, data: bytes) -> None:
        if self._complete:
            return

        if block_num < self._expected_block:
            return

        if block_num > self._expected_block:
            gap = block_num - self._expected_block
            _LOGGER.warning(
                "Title block gap: expected block %d, got %d. Filling %d missing block(s) with placeholders.",
                self._expected_block,
                block_num,
                gap,
            )
            self._buffer.extend(b"_" * (_CONTINUATION_BLOCK_SIZE * gap))

        self._buffer.extend(data)
        self._expected_block = block_num + 1
        self._check_for_null(data)
