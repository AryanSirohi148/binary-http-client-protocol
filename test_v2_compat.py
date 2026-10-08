#!/usr/bin/env python3
"""
test_v2_compat.py - Tests that bcurl cleanly skips unknown frame types.
"""

import socket
import threading
import subprocess
import time
from protocol import Frame, FRAME_HEADERS, FRAME_DATA, FLAG_END_HEADERS, FLAG_END_STREAM, encode_headers

TEST_PORT = 9005

def run_mock_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", TEST_PORT))
    srv.listen(1)

    conn, _ = srv.accept()
    # Read client's request (9-byte header + payload)
    hdr = conn.recv(9)
    length, ftype, flags, stream_id = Frame.unpack_header(hdr)
    payload = conn.recv(length)

    # 1. SEND AN UNKNOWN V2 EXTENSION FRAME FIRST! (Type 0x77, length 12)
    unknown_payload = b"FutureV2Data"
    unknown_frame = Frame(frame_type=0x77, flags=0x00, stream_id=stream_id, payload=unknown_payload)
    conn.sendall(unknown_frame.pack())

    # 2. SEND STANDARD HEADERS FRAME
    headers = [
        (":status", "200"),
        ("content-type", "text/plain"),
        ("content-length", "18"),
    ]
    hdr_frame = Frame(frame_type=FRAME_HEADERS, flags=FLAG_END_HEADERS, stream_id=stream_id, payload=encode_headers(headers))
    conn.sendall(hdr_frame.pack())

    # 3. SEND DATA FRAME
    data_frame = Frame(frame_type=FRAME_DATA, flags=FLAG_END_STREAM, stream_id=stream_id, payload=b"V2 skipping works!")
    conn.sendall(data_frame.pack())

    time.sleep(0.5)
    conn.close()
    srv.close()

if __name__ == "__main__":
    t = threading.Thread(target=run_mock_server, daemon=True)
    t.start()
    time.sleep(0.2)

    res = subprocess.run(["./bcurl", "-v", f"127.0.0.1:{TEST_PORT}/test"], capture_output=True, text=True)
    print("STDOUT:", res.stdout)
    print("STDERR:", res.stderr)
    print("EXIT CODE:", res.returncode)
    assert res.returncode == 0, f"Expected 0, got {res.returncode}"
    assert "V2 skipping works!" in res.stdout, "Payload not found in stdout!"
    assert "Skipped unknown frame type 0x77" in res.stderr, "Verbose skip message not found!"
    print(">>> SUCCESS: bcurl cleanly skipped unknown frame type 0x77 and received data! <<<")
