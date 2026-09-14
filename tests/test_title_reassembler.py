"""Tests for TitleReassembler."""

import logging

from custom_components.sony_a1_bus.devices.title_reassembler import TitleReassembler


class TestTitleReassemblerBasic:
    """Tests for basic TitleReassembler functionality."""

    def test_single_block_complete_with_null(self):
        """Test title complete in first block with null terminator."""
        data = b"Hello World\x00\x00\x00"
        reassembler = TitleReassembler(data)
        assert reassembler.is_complete
        assert reassembler.get_title() == "Hello World"

    def test_single_block_full_14_bytes_no_null(self):
        """Test title not complete when first block is full 14 bytes with no null."""
        data = b"FourteenByte"  # 12 bytes
        data = data + b"!!"  # 14 bytes total, no null
        reassembler = TitleReassembler(data)
        assert not reassembler.is_complete
        assert reassembler.get_title() is None

    def test_single_block_empty(self):
        """Test empty title (null at position 0)."""
        data = b"\x00" + b"\x00" * 13
        reassembler = TitleReassembler(data)
        assert reassembler.is_complete
        assert reassembler.get_title() == ""

    def test_null_at_end_of_block(self):
        """Test title with null at the very end of first block."""
        data = b"ThirteenByte" + b"\x00"  # 13 chars + null = 14 bytes
        reassembler = TitleReassembler(data)
        assert reassembler.is_complete
        assert reassembler.get_title() == "ThirteenByte"


class TestTitleReassemblerMultiBlock:
    """Tests for multi-block title reassembly."""

    def test_two_blocks_with_null_in_second(self):
        """Test title spanning two blocks with null in second block."""
        initial = b"FourteenBytes!"  # 14 bytes, no null
        reassembler = TitleReassembler(initial)
        assert not reassembler.is_complete

        continuation = b"More Text\x00\x00\x00\x00\x00\x00\x00"  # 16 bytes
        reassembler.add_block(2, continuation)
        assert reassembler.is_complete
        assert reassembler.get_title() == "FourteenBytes!More Text"

    def test_three_blocks(self):
        """Test title spanning three blocks."""
        initial = b"A" * 14
        reassembler = TitleReassembler(initial)
        
        reassembler.add_block(2, b"B" * 16)
        assert not reassembler.is_complete
        
        reassembler.add_block(3, b"C" * 10 + b"\x00" * 6)
        assert reassembler.is_complete
        assert reassembler.get_title() == "A" * 14 + "B" * 16 + "C" * 10

    def test_null_in_continuation_terminates(self):
        """Test that null in continuation block terminates title."""
        initial = b"A" * 14
        reassembler = TitleReassembler(initial)
        
        reassembler.add_block(2, b"BCDEFGHIJKLMNOP")  # 16 bytes, no null
        assert not reassembler.is_complete
        
        reassembler.add_block(3, b"End\x00" + b"\x00" * 12)
        assert reassembler.is_complete
        assert reassembler.get_title() == "A" * 14 + "BCDEFGHIJKLMNOP" + "End"

    def test_full_16_byte_continuation_no_null(self):
        """Test continuation block with all 16 bytes and no null."""
        initial = b"A" * 14
        reassembler = TitleReassembler(initial)
        
        reassembler.add_block(2, b"B" * 16)
        assert not reassembler.is_complete
        
        reassembler.add_block(3, b"C" * 16)
        assert not reassembler.is_complete
        
        reassembler.add_block(4, b"Done\x00" + b"\x00" * 11)
        assert reassembler.is_complete
        assert reassembler.get_title() == "A" * 14 + "B" * 16 + "C" * 16 + "Done"


class TestTitleReassemblerIdempotency:
    """Tests for duplicate and out-of-order block handling."""

    def test_duplicate_block_ignored(self):
        """Test that duplicate blocks are silently ignored."""
        initial = b"A" * 14
        reassembler = TitleReassembler(initial)
        
        reassembler.add_block(2, b"B" * 16)
        reassembler.add_block(2, b"X" * 16)  # Duplicate, should be ignored
        
        reassembler.add_block(3, b"End\x00" + b"\x00" * 13)
        assert reassembler.is_complete
        assert reassembler.get_title() == "A" * 14 + "B" * 16 + "End"

    def test_gap_in_blocks_fills_with_placeholders(self, caplog):
        """Test that gaps in block numbering are filled with placeholders."""
        initial = b"A" * 14
        reassembler = TitleReassembler(initial)
        
        with caplog.at_level(logging.WARNING):
            reassembler.add_block(4, b"End\x00" + b"\x00" * 13)
        
        assert reassembler.is_complete
        assert "gap" in caplog.text.lower()
        title = reassembler.get_title()
        assert title == "A" * 14 + "_" * 32 + "End"  # 2 missing blocks * 16 bytes

    def test_add_block_after_complete_ignored(self):
        """Test that blocks added after completion are ignored."""
        initial = b"Hello\x00" + b"\x00" * 8
        reassembler = TitleReassembler(initial)
        assert reassembler.is_complete
        assert reassembler.get_title() == "Hello"
        
        reassembler.add_block(2, b"More\x00" + b"\x00" * 12)
        assert reassembler.get_title() == "Hello"  # Unchanged

    def test_old_block_after_gap_ignored(self):
        """Test that old blocks after a gap are ignored."""
        initial = b"A" * 14
        reassembler = TitleReassembler(initial)
        
        reassembler.add_block(3, b"C" * 16)  # Gap: expected 2, got 3
        reassembler.add_block(2, b"B" * 16)  # Old block, should be ignored
        
        reassembler.add_block(4, b"End\x00" + b"\x00" * 12)
        assert reassembler.is_complete
        title = reassembler.get_title()
        assert "B" not in title  # Block 2 was ignored
        assert title == "A" * 14 + "_" * 16 + "C" * 16 + "End"


class TestTitleReassemblerEncoding:
    """Tests for character encoding handling."""

    def test_ascii_decoded_correctly(self):
        """Test that ASCII characters are decoded correctly."""
        data = b"Test Title\x00\x00\x00\x00"
        reassembler = TitleReassembler(data)
        assert reassembler.get_title() == "Test Title"

    def test_non_ascii_replaced(self):
        """Test that non-ASCII bytes are replaced with replacement character."""
        data = b"Test\x80\x81Title\x00\x00\x00"
        reassembler = TitleReassembler(data)
        title = reassembler.get_title()
        assert "Test" in title
        assert "Title" in title
