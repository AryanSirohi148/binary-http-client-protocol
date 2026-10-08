#!/usr/bin/env python3
"""
bserve - Reference Binary HTTP/1.0 Server Implementation
Course Project: "HTTP, in binary — Two tracks, one protocol"

Usage:
    ./bserve <root_dir> <port>
Example:
    ./bserve ./www 9000
"""

import os
import sys
import socket
import mimetypes
from pathlib import Path
from typing import Optional, Tuple

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


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """Reads exactly num_bytes from the TCP socket."""
    buf = bytearray()
    while len(buf) < num_bytes:
        chunk = sock.recv(num_bytes - len(buf))
        if not chunk:
            if len(buf) == 0:
                return b""  # Connection closed cleanly
            raise ConnectionError("Connection closed unexpectedly during frame read")
        buf.extend(chunk)
    return bytes(buf)


def send_response(sock: socket.socket, stream_id: int, status: int,
                  content_type: str, body: bytes):
    """Sends HEADERS frame followed by DATA frame for a given response."""
    # 1. Response HEADERS frame
    resp_headers = [
        (":status", str(status)),
        ("server", "bserve/1.0"),
        ("content-type", content_type),
        ("content-length", str(len(body))),
    ]
    encoded_hdrs = encode_headers(resp_headers)

    # HEADERS frame carries END_HEADERS
    hdr_frame = Frame(
        frame_type=FRAME_HEADERS,
        flags=FLAG_END_HEADERS if len(body) > 0 else (FLAG_END_HEADERS | FLAG_END_STREAM),
        stream_id=stream_id,
        payload=encoded_hdrs,
    )
    sock.sendall(hdr_frame.pack())

    # 2. Response DATA frame (if body present)
    if len(body) > 0:
        data_frame = Frame(
            frame_type=FRAME_DATA,
            flags=FLAG_END_STREAM,
            stream_id=stream_id,
            payload=body,
        )
        sock.sendall(data_frame.pack())


def handle_client(sock: socket.socket, client_addr: Tuple[str, int], root_dir: Path):
    """
    Main loop for a connected client.
    Handles multiple requests over a single persistent TCP connection.
    """
    print(f"[+] Client connected from {client_addr[0]}:{client_addr[1]}")

    try:
        while True:
            # Read 9-byte frame header
            hdr_raw = recv_exact(sock, HEADER_SIZE)
            if not hdr_raw:
                print(f"[-] Client {client_addr} closed connection cleanly.")
                break

            try:
                length, ftype, flags, stream_id = Frame.unpack_header(hdr_raw)
            except Exception as e:
                print(f"[!] Malformed header received: {e}")
                send_response(sock, 1, 400, "text/plain", b"400 Bad Request: Corrupted frame header\n")
                break

            # Read payload
            payload = recv_exact(sock, length) if length > 0 else b""

            # SPEC RULE: Receivers meeting an unknown frame type MUST skip it cleanly
            if ftype not in (FRAME_DATA, FRAME_HEADERS, FRAME_SETTINGS):
                print(f"[!] Unknown frame type 0x{ftype:02x} encountered. Cleanly skipping {length} bytes.")
                continue

            if ftype != FRAME_HEADERS:
                # In BHTTP GET flow, request begins with HEADERS
                continue

            # Decode request headers
            try:
                headers_list = decode_headers(payload)
                headers_dict = dict(headers_list)
            except Exception as e:
                print(f"[!] Malformed headers block: {e}")
                send_response(sock, stream_id, 400, "text/plain", b"400 Bad Request: Unparseable headers\n")
                continue

            method = headers_dict.get(":method", "GET")
            path_str = headers_dict.get(":path", "/")

            print(f"[*] Request: {method} '{path_str}' on stream {stream_id}")

            # Clean and sanitize path to prevent directory traversal
            clean_rel = path_str.split("?")[0].lstrip("/")
            if not clean_rel or clean_rel.endswith("/"):
                clean_rel += "index.html"

            resolved_path = (root_dir / clean_rel).resolve()

            # Security check: Ensure resolved path stays inside root directory
            if not str(resolved_path).startswith(str(root_dir.resolve())):
                print(f"[-] Forbidden path access attempted: {path_str}")
                send_response(sock, stream_id, 400, "text/plain", b"400 Bad Request: Path traversal denied\n")
                continue

            # Check if file exists
            if resolved_path.is_file():
                try:
                    with open(resolved_path, "rb") as f:
                        file_bytes = f.read()
                    mime, _ = mimetypes.guess_type(str(resolved_path))
                    content_type = mime or "application/octet-stream"
                    send_response(sock, stream_id, 200, content_type, file_bytes)
                    print(f"[+] 200 OK sent ({len(file_bytes)} bytes)")
                except Exception as e:
                    send_response(sock, stream_id, 500, "text/plain", f"500 Internal Error: {e}\n".encode())
            else:
                print(f"[-] 404 Not Found: {resolved_path}")
                send_response(sock, stream_id, 404, "text/plain", b"404 Not Found\n")

            # CONNECTION STAYS OPEN! Loop continues for next request.

    except ConnectionError:
        print(f"[-] Client {client_addr} disconnected.")
    except Exception as e:
        print(f"[!] Exception handling client {client_addr}: {e}")
    finally:
        sock.close()


def main():
    if len(sys.argv) < 3:
        print("Usage: ./bserve <root_dir> <port>")
        print("Example: ./bserve ./www 9000")
        sys.exit(1)

    root_dir = Path(sys.argv[1]).resolve()
    port = int(sys.argv[2])

    if not root_dir.exists():
        print(f"Creating root directory at: {root_dir}")
        root_dir.mkdir(parents=True, exist_ok=True)

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("0.0.0.0", port))
    server_sock.listen(5)

    print(f"=== BHTTP Reference Server (bserve/1.0) ===")
    print(f"Serving directory : {root_dir}")
    print(f"Listening on port : {port}")
    print(f"Connection policy : Keep-Alive / Persistent")
    print(f"Press Ctrl+C to terminate.")

    try:
        while True:
            client_sock, client_addr = server_sock.accept()
            handle_client(client_sock, client_addr, root_dir)
    except KeyboardInterrupt:
        print("\nServer shutting down gracefully.")
    finally:
        server_sock.close()


if __name__ == "__main__":
    main()
