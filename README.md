# BHTTP (Binary HTTP) — Client & Protocol Implementation

A binary application-layer protocol and client implementation built for the **"HTTP, in binary — Two tracks, one protocol"** course project.

This repository implements **Track 2 (The Client — `bcurl`)**, along with the complete protocol specification (`SPEC.md`), an annotated byte-level hexdump (`HEXDUMP.md`), and a reference server (`bserve`) used for verification and end-to-end integration testing.

---

## 💡 Overview & Motivation

Traditional HTTP/1.1 relies on ASCII text delimiters (CRLF, space-delimited headers, textual chunked encoding), which makes parsing CPU-intensive, error-prone, and prone to smuggling vulnerabilities. 

**BHTTP/1.0** takes core architectural concepts from HTTP/2 (RFC 7540) and HPACK (RFC 7541) and adapts them into a lean, elegant binary protocol layered directly over TCP:
- **Fixed-size binary framing:** Every frame starts with an unambiguous 9-byte header.
- **HPACK-lite header compression:** Static indexing for the 10 most common header names, combined with length-prefixed literals.
- **Single TCP connection reuse:** Persistent keep-alive connections that eliminate redundant TCP three-way handshakes.
- **Forward compatibility:** Strictly enforces that receivers encountering unknown frame types must skip them cleanly based on the length field.

---

## 📐 The Framing Layer

Every frame sent over the wire begins with a fixed **9-byte (72-bit)** header:

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

### Defending the Field Widths (`24 / 8 / 8 / 31`)
- **Length (24 bits):** Caps any single frame payload at 16 MB ($2^{24}-1$). This prevents malicious actors from exhausting socket buffers with massive allocations, while completely avoiding the severe 64 KB fragmentation penalty of 16-bit lengths.
- **Type (8 bits):** Supports up to 256 frame types (`0x00` DATA, `0x01` HEADERS, `0x04` SETTINGS, etc.), leaving ample space for future protocol extensions.
- **Flags (8 bits):** Dedicated bitmask flags per frame type (`0x01` `END_STREAM`, `0x04` `END_HEADERS`).
- **Stream ID (31 bits + 1 reserved):** Allows stream identifiers up to $2^{31}-1$, preventing ID rollover during long-lived persistent TCP connections.

---

## 🗂️ Project Structure

```
.
├── SPEC.md             # The complete 2-page BHTTP/1.0 protocol specification
├── HEXDUMP.md          # Annotated byte-by-byte hexdump of request & response
├── bcurl               # Binary client executable (Track 2)
├── bcurl.py            # Client source code
├── protocol.py         # Shared framing logic, HPACK static tables & serializers
├── bserve              # Reference server executable (Track 1, for testing)
├── bserve.py           # Server source code
├── test_v2_compat.py   # Test suite verifying forward compatibility (V2 unknown frame skip)
└── www/                # Document root for testing
    ├── index.html
    └── hello.txt
```

---

## 🛠️ Usage

### 1. Running the Client (`bcurl`)

The client implements all requirements specified in Track 2:

```bash
# Basic request: prints response body to stdout
./bcurl localhost:9000/index.html

# Verbose mode: prints detailed frame metadata and hexdumps to stderr
./bcurl -v localhost:9000/index.html

# Piped to file (binary-safe output):
./bcurl localhost:9000/index.html > output.html

# Persistent connection demonstration (fetches multiple paths across ONE connection):
./bcurl -v localhost:9000/hello.txt localhost:9000/index.html
```

#### Client Invariants & Features:
- **Single Connection Reuse:** Connects once upon startup and reuses the exact same TCP socket for every transaction. Never opens a second connection.
- **Verbose Output (`-v`):** Hexdumps every outgoing and incoming frame with byte offsets and ASCII decoding to `stderr`, keeping `stdout` completely clean for redirected output.
- **Exit Codes:** Returns exit code `0` on 2xx/3xx, exit code `4` on 4xx (e.g. 404), and exit code `5` on 5xx.

---

### 2. Running the Reference Server (`bserve`)

To test locally or with partners:

```bash
# Start server with root directory and port
./bserve ./www 9000
```

The server keeps client TCP connections open, maps incoming paths under `./www`, responds with `HEADERS` and `DATA` frames, returns 404 for missing paths, and validates paths against directory traversal attacks.

---

## 🧪 Testing & Validation

### Automated V2 Forward Compatibility Test
The spec mandates that *a receiver meeting an unknown frame type must skip it cleanly*. We built an automated test that injects an unassigned extension frame (`0x77`) with a custom payload prior to standard response frames:

```bash
python3 test_v2_compat.py
```

Expected output:
```
* [V2 COMPAT] Skipped unknown frame type 0x77 (12 bytes) cleanly.
STDOUT: V2 skipping works!
>>> SUCCESS: bcurl cleanly skipped unknown frame type 0x77 and received data! <<<
```

---

## 📝 Hand-in Deliverables Summary

1. **The Spec (`SPEC.md`):** Complete two-page specification defining the frame layout, field defense, HPACK-lite tables, and state transitions.
2. **The Program (`bcurl`):** Executable Python client meeting all Track 2 specifications.
3. **Annotated Hexdump (`HEXDUMP.md`):** Fully annotated request and response frames detailing every single byte on the wire.
