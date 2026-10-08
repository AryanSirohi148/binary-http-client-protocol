# Binary HTTP (BHTTP/1.0) - Client & Server Implementation

Computer Networks Course Project: Binary HTTP Protocol

This repository contains a full implementation of the **Binary HTTP (BHTTP/1.0)** protocol, covering both **Track 1 (The Server: `bserve`)** and **Track 2 (The Client: `bcurl`)**, along with the formal protocol specification (`SPEC.md`), byte-level frame breakdown (`HEXDUMP.md`), and end-to-end integration tests (`test_all.py`).

Both tracks were built and tested together over real TCP sockets to verify that the client and server communicate reliably across multiple requests.

---

## 1. Project Overview

Traditional HTTP/1.1 uses text-based parsing with CRLF (`\r\n`) delimiters, which adds parsing overhead and is susceptible to request-smuggling attacks. BHTTP/1.0 replaces ASCII delimiters with fixed binary framing inspired by HTTP/2, running directly over TCP.

Key design points:
- **9-byte fixed header:** Every frame starts with a 72-bit header containing the payload length, frame type, flags, and stream identifier.
- **HPACK-lite header compression:** Uses a static table of 10 common headers with 1-byte indices, followed by length-prefixed literal values.
- **Persistent connection reuse:** Clients open a single TCP socket and reuse it for multiple sequential requests. The server maintains the connection open.
- **Forward compatibility:** Unknown frame types are skipped cleanly using the 24-bit length field without terminating the connection.

---

## 2. Framing Layer Design

Every frame on the wire begins with a fixed 9-byte header:

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                         Length (24)                           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   Type (8)    |   Flags (8)   |R|          Stream ID (31)     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                     Stream ID (cont.)                         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                     Payload (0 ... 2^24-1)                  ...
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### Rationale for Field Sizes (24 / 8 / 8 / 31)
- **Length (24 bits):** Allows payload sizes up to 16 MB ($2^{24} - 1$ bytes). 16-bit lengths (64 KB) would cause excessive fragmentation for common files, while 32-bit lengths would risk uncontrolled buffer allocations. 24 bits provides a safe balance.
- **Type (8 bits):** Allows up to 256 frame types (`0x00` DATA, `0x01` HEADERS, `0x04` SETTINGS, etc.), leaving space for future extensions.
- **Flags (8 bits):** Frame-specific bitmasks (`0x01` for `END_STREAM`, `0x04` for `END_HEADERS`).
- **Stream ID (31 bits + 1 reserved bit):** Supports up to $2^{31} - 1$ streams over a single long-lived connection without ID rollover.

---

## 3. Repository Structure

```
.
├── SPEC.md             # Complete protocol specification
├── HEXDUMP.md          # Annotated byte-by-byte hexdump of request and response
├── protocol.py         # Shared binary framing logic and HPACK-lite codec
├── bserve              # Server executable (Track 1)
├── bserve.py           # Server Python source
├── bcurl               # Client executable (Track 2)
├── bcurl.py            # Client Python source
├── test_all.py         # End-to-end integration test suite (runs both tracks)
├── test_v2_compat.py   # Forward compatibility test (skipping unknown frame types)
└── www/                # Sample static documents for testing
    ├── index.html
    └── hello.txt
```

---

## 4. Track 1: Server (`bserve`)

The server satisfies all requirements from the Track 1 assignment specification:
- Accepts TCP connections on the specified port.
- Reads binary request frames.
- Maps the requested path to a file inside the root directory (`./www`).
- Prevents directory traversal attacks (`../` is rejected).
- Responds with `HEADERS` frame (`:status`, `content-type`, `content-length`, `server`) followed by `DATA` frame containing file bytes.
- Returns `404 Not Found` if the file does not exist.
- Returns `400 Bad Request` if a frame or header block is malformed.
- Keeps connections open across requests (persistent connection).

### Starting the Server
```bash
./bserve ./www 9000
```
Or with python:
```bash
python3 bserve.py ./www 9000
```

---

## 5. Track 2: Client (`bcurl`)

The client satisfies all requirements from the Track 2 assignment specification:
- Connects to the host and port over a single TCP socket.
- Encodes a binary `HEADERS` request frame with `END_STREAM | END_HEADERS`.
- Streams response `DATA` bytes directly to `stdout` (binary safe for file redirection).
- Exits with a non-zero exit code if the server returns a 4xx or 5xx status code.
- Verbose mode (`-v`): prints connection info, decoded headers, and full packet hexdumps to `stderr` so stdout remains clean for piping.
- Persistent connection: fetches multiple paths across the same connection without opening a second TCP socket.

### Running the Client

Basic request (outputs file body to stdout):
```bash
./bcurl localhost:9000/hello.txt
```

Verbose mode (annotated frames printed to stderr):
```bash
./bcurl -v localhost:9000/hello.txt
```

Redirecting output to a file:
```bash
./bcurl localhost:9000/index.html > output.html
```

Fetching multiple files over a single TCP connection:
```bash
./bcurl -v localhost:9000/hello.txt localhost:9000/index.html
```

Testing error handling (404):
```bash
./bcurl localhost:9000/nonexistent.txt
echo $?  # returns non-zero (4)
```

---

## 6. Testing and Verification

To verify that both the client and server work properly together, two automated test scripts are provided:

### 1. Complete End-to-End Test Suite (`test_all.py`)
This script launches `bserve` on a local port, runs `bcurl` and raw socket clients against it, and checks all functional requirements:
- Test 1: Successful 200 OK file delivery (`/hello.txt`).
- Test 2: HTML file delivery (`/index.html`).
- Test 3: 404 Not Found handling and non-zero exit code.
- Test 4: Persistent connection reuse across multiple streams (Stream 1 and 3 on the same TCP socket).
- Test 5: Verbose hexdump output verification.
- Test 6: 400 Bad Request handling on corrupt frame data.

Run the test suite:
```bash
python3 test_all.py
```

Expected output:
```
============================================================
  Starting BHTTP End-to-End Verification
============================================================
[Test 1] GET /hello.txt (Expect 200 OK and exact file content)...
  [PASS] 200 OK received with exact file body.
[Test 2] GET /index.html (Expect 200 OK and HTML body)...
  [PASS] HTML delivered accurately.
[Test 3] GET /missing_file.txt (Expect 404 and exit non-zero)...
  [PASS] Server returned 404, client exited with code 4 (non-zero as required).
[Test 4] Multi-file request over ONE single TCP connection...
  [PASS] Both requests served over the SAME socket on streams 1 & 3.
[Test 5] bcurl -v flag hexdumps every frame to stderr...
  [PASS] Formatted frame headers and hex offsets verified in stderr.
[Test 6] Server 400 Bad Request on corrupted headers payload...
  [PASS] Server returned 400 Bad Request for unparseable headers.
============================================================
  RESULTS: 6/6 Tests Passed Successfully!
============================================================
```

### 2. Forward Compatibility Test (`test_v2_compat.py`)
Verifies that `bcurl` correctly ignores unknown extension frame types (e.g. `0x77`) without crashing or aborting:
```bash
python3 test_v2_compat.py
```

---

## 7. Deliverables Checklist

- [x] **Specification (`SPEC.md`):** Complete protocol specification covering 9-byte framing, field width rationale (24/8/8/31), HPACK-lite static table, flags, and connection states.
- [x] **Client Program (`bcurl` / `bcurl.py`):** Working binary client with verbose logging, persistent connection reuse, and non-zero error exits.
- [x] **Server Program (`bserve` / `bserve.py`):** Working binary server with directory mapping, 200/404/400 handling, and persistent connection loops.
- [x] **Annotated Hexdump (`HEXDUMP.md`):** Byte-by-byte dissection of a live request/response exchange with offset tables.
- [x] **Automated Tests (`test_all.py`, `test_v2_compat.py`):** Reproducible test cases verifying end-to-end behavior.
