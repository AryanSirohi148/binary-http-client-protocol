#!/usr/bin/env python3
"""
bcurl - Binary HTTP/1.0 Client Implementation
Course Project: "HTTP, in binary — Two tracks, one protocol"

Usage:
    ./bcurl [-v] <host:port/path> [<host:port/path> ...]
Example:
    ./bcurl -v localhost:9000/index.html
"""

import sys
import socket
import struct
from urllib.parse import urlparse
from typing import List, Tuple, Optional

# Import BHTTP framing and codec definitions
from protocol import (
    FRAME_DATA,
    FRAME_HEADERS,
    FRAME_SETTINGS,
    FLAG_END_STREAM,
    FLAG_END_HEADERS,
    HEADER_SIZE,
    Frame,
    encode_headers,
    decode_headers,
    format_hexdump,
)


def log_verbose(msg: str):
    """Logs verbose diagnostic info to stderr (curl style)."""
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def parse_target_url(target: str) -> Tuple[str, int, str]:
    """
    Parses a target string into (host, port, path).
    Accepts formats like:
      - localhost:9000/index.html
      - 127.0.0.1:9000/
      - http://localhost:9000/test.txt
      - localhost:9000
    """
    raw = target.strip()
    if not (raw.startswith("http://") or raw.startswith("https://") or raw.startswith("bhttp://")):
        raw = "bhttp://" + raw

    parsed = urlparse(raw)
    host = parsed.hostname or "localhost"
    port = parsed.port if parsed.port is not None else 9000
    path = parsed.path if parsed.path else "/"
    if parsed.query:
        path += "?" + parsed.query
    return host, port, path


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """Reads exactly num_bytes from the TCP socket, handling TCP segmentation."""
    buf = bytearray()
    while len(buf) < num_bytes:
        chunk = sock.recv(num_bytes - len(buf))
        if not chunk:
            if len(buf) == 0:
                return b""  # Clean EOF at frame boundary
            raise ConnectionError(
                f"Connection closed unexpectedly after {len(buf)}/{num_bytes} bytes"
            )
        buf.extend(chunk)
    return bytes(buf)


def dump_frame_verbose(direction: str, frame: Frame):
    """Prints a detailed, annotated hexdump of a frame to stderr."""
    raw_frame = frame.pack()
    hdr_bytes = raw_frame[:HEADER_SIZE]
    payload_bytes = raw_frame[HEADER_SIZE:]

    arrow = ">" if direction == "SENT" else "<"
    log_verbose(f"* {arrow} [FRAME {direction}] Type: {frame.type_name()} (0x{frame.type:02x}) | "
                f"Flags: {frame.flag_names()} (0x{frame.flags:02x}) | "
                f"Stream: {frame.stream_id} | Length: {frame.length} bytes")
    
    # Hexdump entire frame
    log_verbose(format_hexdump(raw_frame, prefix="* "))


def execute_request(sock: socket.socket, host: str, port: int, path: str,
                    stream_id: int, verbose: bool) -> int:
    """
    Issues one binary request frame over the active connection,
    reads response frames, writes response body to stdout,
    and returns the integer HTTP status code.
    """
    # 1. Build Request Headers
    req_headers = [
        (":method", "GET"),
        (":path", path),
        ("host", f"{host}:{port}"),
        ("user-agent", "bcurl/1.0"),
        ("accept", "*/*"),
    ]
    encoded_payload = encode_headers(req_headers)

    # Request frame: HEADERS with END_STREAM and END_HEADERS
    req_frame = Frame(
        frame_type=FRAME_HEADERS,
        flags=FLAG_END_STREAM | FLAG_END_HEADERS,
        stream_id=stream_id,
        payload=encoded_payload,
    )

    if verbose:
        log_verbose(f"* Requesting path: '{path}' on Stream {stream_id}")
        dump_frame_verbose("SENT", req_frame)

    # Send the frame over the TCP connection
    sock.sendall(req_frame.pack())

    # 2. Read Response Frames
    status_code: Optional[int] = None
    stream_ended = False

    while not stream_ended:
        hdr_raw = recv_exact(sock, HEADER_SIZE)
        if not hdr_raw:
            if status_code is None:
                raise ConnectionError("Server closed connection before sending response headers")
            break

        length, ftype, flags, frame_stream_id = Frame.unpack_header(hdr_raw)
        payload = recv_exact(sock, length) if length > 0 else b""

        frame = Frame(ftype, flags, frame_stream_id, payload)

        if verbose:
            dump_frame_verbose("RECV", frame)

        # SPEC RULE: A receiver meeting a frame type it does not know MUST skip it cleanly.
        if ftype not in (FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS):
            if verbose:
                log_verbose(f"* [V2 COMPAT] Skipped unknown frame type 0x{ftype:02x} ({length} bytes) cleanly.")
            continue

        # Handle SETTINGS / PING
        if ftype == FRAME_SETTINGS:
            if verbose:
                log_verbose("* Received SETTINGS / Control frame; processed and continued.")
            continue

        # Ignore frames intended for different streams if any
        if frame_stream_id != stream_id:
            if verbose:
                log_verbose(f"* Ignoring frame for stream {frame_stream_id} (current: {stream_id})")
            continue

        # Handle HEADERS frame
        if ftype == FRAME_HEADERS:
            headers = decode_headers(payload)
            for name, val in headers:
                if name == ":status":
                    try:
                        status_code = int(val)
                    except ValueError:
                        status_code = 500
                if verbose:
                    log_verbose(f"< {name}: {val}")

            if flags & FLAG_END_STREAM:
                stream_ended = True

        # Handle DATA frame
        elif ftype == FRAME_DATA:
            if payload:
                # Body bytes go cleanly to stdout (binary safe)
                sys.stdout.buffer.write(payload)
                sys.stdout.buffer.flush()

            if flags & FLAG_END_STREAM:
                stream_ended = True

    if status_code is None:
        log_verbose("Error: Response finished without a ':status' header.")
        return 500

    return status_code


def main():
    args = sys.argv[1:]
    verbose = False

    # Extract -v / --verbose
    cleaned_args = []
    for arg in args:
        if arg in ("-v", "--verbose"):
            verbose = True
        else:
            cleaned_args.append(arg)

    if not cleaned_args:
        sys.stderr.write("Usage: ./bcurl [-v] <host:port/path> [additional_paths...]\n")
        sys.stderr.write("Example: ./bcurl -v localhost:9000/index.html\n")
        sys.exit(1)

    # Parse primary target for initial connection
    first_target = cleaned_args[0]
    primary_host, primary_port, _ = parse_target_url(first_target)

    # Establish ONE single TCP connection (Invariant: never open a second connection)
    if verbose:
        log_verbose(f"* Connecting to {primary_host}:{primary_port} (Single TCP Connection)")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((primary_host, primary_port))
    except Exception as e:
        sys.stderr.write(f"Error: Could not connect to {primary_host}:{primary_port}: {e}\n")
        sys.exit(1)

    overall_exit_code = 0
    stream_id = 1

    try:
        # Process each requested target sequentially across the SAME connection
        for target in cleaned_args:
            host, port, path = parse_target_url(target)
            if (host, port) != (primary_host, primary_port):
                sys.stderr.write(
                    f"Warning: Target '{target}' points to a different host/port. "
                    f"Rule: bcurl never opens a second connection. Skipping.\n"
                )
                continue

            status = execute_request(sock, host, port, path, stream_id, verbose)
            stream_id += 2  # Client uses odd stream IDs (1, 3, 5...)

            # Exit non-zero on 4xx / 5xx
            if status >= 400:
                if verbose:
                    log_verbose(f"* Server returned HTTP status {status} (Error)")
                if overall_exit_code == 0:
                    overall_exit_code = 4 if (400 <= status < 500) else 5

    except BrokenPipeError:
        sys.stderr.write("Error: Broken pipe - connection terminated by remote server.\n")
        overall_exit_code = 1
    except Exception as e:
        sys.stderr.write(f"Error during protocol exchange: {e}\n")
        overall_exit_code = 1
    finally:
        # Cleanly shut down the single socket on exit
        try:
            sock.close()
        except Exception:
            pass

    sys.exit(overall_exit_code)


if __name__ == "__main__":
    main()
