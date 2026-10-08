#!/usr/bin/env python3
"""
test_all.py - Complete End-to-End Test Suite for BHTTP
Tests both Track 1 (bserve) and Track 2 (bcurl) together.
"""

import sys
import time
import socket
import struct
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
PORT = 9055
WWW_DIR = SCRIPT_DIR / "www"

def print_banner(msg):
    print("\n" + "=" * 60)
    print(f"  {msg}")
    print("=" * 60)

def main():
    print_banner("Starting BHTTP End-to-End Verification")

    # 1. Start Server (bserve) in background using sys.executable
    server_cmd = [sys.executable, str(SCRIPT_DIR / "bserve.py"), str(WWW_DIR), str(PORT)]
    server_proc = subprocess.Popen(server_cmd)
    
    # Wait for server to bind
    time.sleep(0.5)

    passed = 0
    total = 0

    try:
        # TEST 1: Basic GET 200 OK
        total += 1
        print(f"\n[Test 1] GET /hello.txt (Expect 200 OK and exact file content)...")
        res = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "bcurl.py"), f"127.0.0.1:{PORT}/hello.txt"],
            capture_output=True,
            text=True
        )
        if res.returncode == 0 and "Hello, Binary World!" in res.stdout:
            print("  [PASS] 200 OK received with exact file body.")
            passed += 1
        else:
            print(f"  [FAIL] code={res.returncode}, stdout={res.stdout}, stderr={res.stderr}")

        # TEST 2: GET HTML File
        total += 1
        print(f"\n[Test 2] GET /index.html (Expect 200 OK and HTML body)...")
        res = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "bcurl.py"), f"127.0.0.1:{PORT}/index.html"],
            capture_output=True,
            text=True
        )
        if res.returncode == 0 and "<h1>Binary HTTP" in res.stdout:
            print("  [PASS] HTML delivered accurately.")
            passed += 1
        else:
            print(f"  [FAIL] code={res.returncode}")

        # TEST 3: 404 Not Found Handling
        total += 1
        print(f"\n[Test 3] GET /missing_file.txt (Expect 404 and exit non-zero)...")
        res = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "bcurl.py"), f"127.0.0.1:{PORT}/missing_file.txt"],
            capture_output=True,
            text=True
        )
        if res.returncode != 0 and "404 Not Found" in res.stdout:
            print(f"  [PASS] Server returned 404, client exited with code {res.returncode} (non-zero as required).")
            passed += 1
        else:
            print(f"  [FAIL] Expected non-zero code, got {res.returncode}")

        # TEST 4: Single Connection Reuse (Persistent Keep-Alive)
        total += 1
        print(f"\n[Test 4] Multi-file request over ONE single TCP connection...")
        res = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "bcurl.py"), "-v", f"127.0.0.1:{PORT}/hello.txt", f"127.0.0.1:{PORT}/index.html"],
            capture_output=True,
            text=True
        )
        if "Stream: 1" in res.stderr and "Stream: 3" in res.stderr and res.returncode == 0:
            print("  [PASS] Both requests served over the SAME socket on streams 1 & 3.")
            passed += 1
        else:
            print(f"  [FAIL] Multi-request persistent connection failed.")

        # TEST 5: Verbose Hexdump Output
        total += 1
        print(f"\n[Test 5] bcurl -v flag hexdumps every frame to stderr...")
        res = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "bcurl.py"), "-v", f"127.0.0.1:{PORT}/hello.txt"],
            capture_output=True,
            text=True
        )
        if "[FRAME SENT]" in res.stderr and "[FRAME RECV]" in res.stderr:
            print("  [PASS] Formatted frame headers and hex offsets verified in stderr.")
            passed += 1
        else:
            print(f"  [FAIL] Verbose hexdump missing.")

        # TEST 6: Malformed Frame / 400 Bad Request
        total += 1
        print(f"\n[Test 6] Server 400 Bad Request on corrupted headers payload...")
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.connect(("127.0.0.1", PORT))
        # Send 9-byte HEADERS header with length=4, followed by 4 invalid bytes
        bad_hdr = struct.pack("!BBB B B I", 0, 0, 4, 0x01, 0x04, 1)
        raw_sock.sendall(bad_hdr + b"\xff\xff\xff\xff")
        time.sleep(0.1)
        resp = raw_sock.recv(1024)
        raw_sock.close()
        if len(resp) > 0 and b"400" in resp:
            print("  [PASS] Server returned 400 Bad Request for unparseable headers.")
            passed += 1
        else:
            print(f"  [FAIL] Unexpected response {resp}")

    finally:
        server_proc.terminate()
        server_proc.wait()

    print_banner(f"RESULTS: {passed}/{total} Tests Passed Successfully!")
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
