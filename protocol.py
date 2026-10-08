"""
protocol.py - Binary HTTP (BHTTP/1.0) Protocol Definitions and Codecs

Defines the 9-byte fixed frame header format, static header table (HPACK-lite),
and serialization/deserialization utilities.
"""

import struct
from typing import Dict, List, Tuple, Optional

# --- Frame Types ---
FRAME_DATA = 0x00
FRAME_HEADERS = 0x01
FRAME_SETTINGS = 0x04

FRAME_TYPE_NAMES = {
    FRAME_DATA: "DATA",
    FRAME_HEADERS: "HEADERS",
    FRAME_SETTINGS: "SETTINGS",
}

# --- Frame Flags ---
FLAG_END_STREAM = 0x01   # Bit 0
FLAG_END_HEADERS = 0x04  # Bit 2

# --- Header Static Table (HPACK-Lite 10 Entries) ---
STATIC_TABLE: Dict[int, str] = {
    1: ":method",
    2: ":path",
    3: ":status",
    4: "host",
    5: "user-agent",
    6: "content-type",
    7: "content-length",
    8: "accept",
    9: "server",
    10: "date",
}

# Reverse mapping for fast encoding
NAME_TO_INDEX: Dict[str, int] = {v: k for k, v in STATIC_TABLE.items()}

# Frame Header: 9 bytes
# 24-bit length, 8-bit type, 8-bit flags, 1-bit reserved + 31-bit stream_id
HEADER_SIZE = 9


class Frame:
    """Represents a single BHTTP frame."""

    def __init__(self, frame_type: int, flags: int, stream_id: int, payload: bytes = b""):
        self.type = frame_type
        self.flags = flags
        self.stream_id = stream_id & 0x7FFFFFFF
        self.payload = payload

    @property
    def length(self) -> int:
        return len(self.payload)

    def pack(self) -> bytes:
        """Serializes frame header + payload into wire bytes."""
        payload_len = self.length
        if payload_len > 0xFFFFFF:
            raise ValueError(f"Payload exceeds 24-bit maximum: {payload_len} bytes")

        # Pack 3-byte length (24-bit big endian)
        len_high = (payload_len >> 16) & 0xFF
        len_mid = (payload_len >> 8) & 0xFF
        len_low = payload_len & 0xFF

        # Pack header: 3 bytes length, 1 byte type, 1 byte flags, 4 bytes stream_id
        hdr = struct.pack("!BBB B B I", len_high, len_mid, len_low, self.type, self.flags, self.stream_id)
        return hdr + self.payload

    @classmethod
    def unpack_header(cls, hdr_bytes: bytes) -> Tuple[int, int, int, int]:
        """
        Parses 9-byte header.
        Returns: (length, type, flags, stream_id)
        """
        if len(hdr_bytes) != HEADER_SIZE:
            raise ValueError(f"Expected 9 bytes for frame header, got {len(hdr_bytes)}")

        b0, b1, b2, ftype, flags, raw_stream = struct.unpack("!BBB B B I", hdr_bytes)
        length = (b0 << 16) | (b1 << 8) | b2
        stream_id = raw_stream & 0x7FFFFFFF
        return length, ftype, flags, stream_id

    def flag_names(self) -> str:
        flags_set = []
        if self.flags & FLAG_END_STREAM:
            flags_set.append("END_STREAM")
        if self.flags & FLAG_END_HEADERS:
            flags_set.append("END_HEADERS")
        return "|".join(flags_set) if flags_set else "0x00"

    def type_name(self) -> str:
        return FRAME_TYPE_NAMES.get(self.type, f"UNKNOWN(0x{self.type:02x})")


def encode_headers(headers: List[Tuple[str, str]]) -> bytes:
    """
    Encodes a list of (name, value) tuples into the BHTTP binary payload.
    Format:
      [2-byte count]
      For each header:
        If static: [1-byte index (1-10)]
        If literal: [0x00] [1-byte name_len] [name bytes]
        [2-byte val_len] [value bytes]
    """
    out = bytearray()
    out.extend(struct.pack("!H", len(headers)))

    for name, value in headers:
        name_lower = name.lower()
        val_bytes = value.encode("utf-8")
        if len(val_bytes) > 0xFFFF:
            raise ValueError(f"Header value too long: {len(val_bytes)} bytes")

        if name_lower in NAME_TO_INDEX:
            idx = NAME_TO_INDEX[name_lower]
            out.append(idx)
        else:
            name_bytes = name_lower.encode("ascii")
            if len(name_bytes) > 0xFF:
                raise ValueError(f"Custom header name too long: {len(name_bytes)} bytes")
            out.append(0x00)
            out.append(len(name_bytes))
            out.extend(name_bytes)

        out.extend(struct.pack("!H", len(val_bytes)))
        out.extend(val_bytes)

    return bytes(out)


def decode_headers(payload: bytes) -> List[Tuple[str, str]]:
    """
    Decodes a binary headers payload into a list of (name, value) tuples.
    """
    if len(payload) < 2:
        raise ValueError("Malformed headers payload: less than 2 bytes")

    num_headers = struct.unpack_from("!H", payload, 0)[0]
    offset = 2
    headers: List[Tuple[str, str]] = []

    for _ in range(num_headers):
        if offset >= len(payload):
            raise ValueError("Unexpected end of payload while decoding headers")

        idx = payload[offset]
        offset += 1

        if idx != 0:
            if idx not in STATIC_TABLE:
                raise ValueError(f"Invalid static header index: {idx}")
            name = STATIC_TABLE[idx]
        else:
            if offset >= len(payload):
                raise ValueError("Truncated header name length")
            name_len = payload[offset]
            offset += 1
            if offset + name_len > len(payload):
                raise ValueError("Truncated literal header name")
            name = payload[offset:offset + name_len].decode("ascii", errors="replace")
            offset += name_len

        if offset + 2 > len(payload):
            raise ValueError("Truncated header value length")
        val_len = struct.unpack_from("!H", payload, offset)[0]
        offset += 2

        if offset + val_len > len(payload):
            raise ValueError("Truncated header value")
        val = payload[offset:offset + val_len].decode("utf-8", errors="replace")
        offset += val_len

        headers.append((name, val))

    return headers


def format_hexdump(data: bytes, prefix: str = "  ") -> str:
    """Produces canonical hex + ASCII dump formatted with line offsets."""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        hex_parts = [f"{b:02x}" for b in chunk]
        # Group into 8 and 8
        if len(hex_parts) > 8:
            hex_str = " ".join(hex_parts[:8]) + "  " + " ".join(hex_parts[8:])
        else:
            hex_str = " ".join(hex_parts)
        # Pad hex string to 49 characters (16 bytes * 3 - 1 + 1 extra space)
        hex_padded = f"{hex_str:<49}"
        ascii_chars = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{prefix}{i:04x}:  {hex_padded}  |{ascii_chars}|")
    return "\n".join(lines)
