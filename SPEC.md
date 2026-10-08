# Binary HTTP Protocol Specification (BHTTP/1.0)
**Document Version:** 1.0  
**Status:** Working Specification — Course Project  
**Authors:** Track 1 (Server) & Track 2 (Client) Pairing  

---

## 1. Overview & Protocol Goals

BHTTP/1.0 is an application-layer binary framing protocol layered directly over a reliable transport stream (TCP). It draws architectural lessons from HTTP/1.1 and HTTP/2 to replace textual delimiters with compact, unambiguous binary frames while preserving HTTP request/response semantics.

### Key Architectural Invariants
1. **Single Connection Reuse:** A client establishes a single TCP connection and reuses it for all subsequent transactions with that host. A client MUST NOT open a second connection.
2. **Persistent by Default:** Connections remain open across request/response exchanges until explicitly terminated by the transport layer or a connection error.
3. **Forward Compatibility & Extensibility:** Any receiver encountering an unknown or unsupported frame type **MUST** read the frame length and skip the payload cleanly without terminating the connection or generating protocol errors.

---

## 2. Binary Framing Layer

All communication consists of discrete binary frames. Every frame begins with a fixed **9-byte (72-bit)** header, followed by a variable-length payload.

### 2.1 Fixed Frame Header Layout

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

### 2.2 Field Definitions & Width Rationale (Defending the 24 / 8 / 8 / 31 Design)

| Field | Width | Description | Rationale |
|---|---|---|---|
| **Length** | 24 bits (3 bytes) | Big-endian unsigned int. Size of payload in bytes ($0$ to $16,777,215$, or $16\text{ MB}$). Excludes the 9-byte header. | 24 bits caps single-frame memory allocation at 16MB. This prevents malicious or malformed packets from inducing unbounded allocation crashes while avoiding 16-bit payload constraints (which would force excessive fragmentation for files $>64\text{ KB}$). |
| **Type** | 8 bits (1 byte) | Identifier determining the format and interpretation of the payload. | 8 bits provides up to 256 distinct frame types, giving ample room for future extensions without wasting header space. |
| **Flags** | 8 bits (1 byte) | Frame-type specific bitmask modifiers. | 8 independent boolean flags per frame type. |
| **Reserved (R)**| 1 bit | Must be set to `0` upon transmission and ignored upon receipt. | Reserved for future stream priority / flow-control signaling. |
| **Stream ID** | 31 bits | Big-endian unsigned int identifying the stream ($1$ to $2^{31}-1$). Stream `0` is reserved for control frames. | 31 bits prevents stream ID rollover during long-lived persistent TCP sessions. In sequential request/response mode, the client initiates requests on odd-numbered streams (e.g., 1, 3, 5...). |

---

## 3. Frame Types & Flags

### 3.1 Frame Type Registry

| Type ID | Name | Description |
|---|---|---|
| `0x00` | **DATA** | Carries raw binary payload bytes (e.g. response body). |
| `0x01` | **HEADERS** | Carries encoded header metadata (method, path, status, headers). |
| `0x04` | **SETTINGS** | Connection configuration / keep-alive ping. |
| `0x05`–`0xFF` | **EXTENSION / RESERVED** | Unrecognized frame types (must be cleanly skipped). |

### 3.2 Defined Flags

- **`END_STREAM` (`0x01`):**  
  Bit 0 of Flags. When set, indicates that this frame is the final frame sent by the sender for the designated stream.
  - A GET request sends a `HEADERS` frame with `END_STREAM = 0x01` (no body).
  - A response sends `HEADERS` (`END_STREAM = 0x00`), followed by `DATA` (`END_STREAM = 0x01`). For zero-length responses, `HEADERS` may directly carry `END_STREAM = 0x01`.
- **`END_HEADERS` (`0x04`):**  
  Bit 2 of Flags. When set, indicates that this frame contains the entirety of the header block. In BHTTP/1.0, all headers fit into one frame, so this flag is always set on `HEADERS` frames.

---

## 4. Header Compression & Encoding (HPACK-Lite)

BHTTP/1.0 implements the first two core mechanisms of HPACK (RFC 7541):
1. **Static Table Indexing:** A static table numbers the 10 most frequently used header names using 1-byte indices ($1$ to $10$).
2. **Length-Prefixed Literal Strings:** Custom/unindexed header names and all header values are encoded with explicit length prefixes.

### 4.1 Static Table (Predefined Header Names)

| Index (Hex / Dec) | Header Name |
|---|---|
| `0x01` (1) | `:method` |
| `0x02` (2) | `:path` |
| `0x03` (3) | `:status` |
| `0x04` (4) | `host` |
| `0x05` (5) | `user-agent` |
| `0x06` (6) | `content-type` |
| `0x07` (7) | `content-length` |
| `0x08` (8) | `accept` |
| `0x09` (9) | `server` |
| `0x0A` (10) | `date` |

### 4.2 Header Block Payload Wire Format

A `HEADERS` frame payload begins with a 2-byte header count, followed by each encoded header pair:

```
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|       Num Headers (16)        |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|        Header Entry 1 ...     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|        Header Entry 2 ...     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

Each **Header Entry** is structured as follows:

1. **Header Name:**
   - **Indexed Name (`1 <= index <= 10`):**
     Represented as a single byte containing the static index `0x01` through `0x0A`.
   - **Literal Name (`index == 0x00`):**
     Byte `0x00`, followed by:
     - `1 byte`: Length of name in bytes ($N$).
     - `$N$ bytes`: ASCII / UTF-8 name string.

2. **Header Value:**
   - Always represented as a length-prefixed string:
     - `2 bytes` (big-endian unsigned short): Length of value in bytes ($V$).
     - `$V$ bytes`: ASCII / UTF-8 value string.

---

## 5. Request & Response Lifecycle

### 5.1 Request Structure (Client -> Server)
A standard GET request is issued on a newly allocated odd Stream ID (starting at 1):
- **Frame Type:** `HEADERS` (`0x01`)
- **Flags:** `END_STREAM | END_HEADERS` (`0x05`)
- **Headers Included:**
  - `:method` -> `"GET"`
  - `:path` -> `"/index.html"`
  - `host` -> `"localhost:9000"`
  - `user-agent` -> `"bcurl/1.0"`

### 5.2 Response Structure (Server -> Client)
On receiving a valid request, the server evaluates the path under the configured root directory:
1. **Success (200 OK):**
   - Server sends `HEADERS` (`0x01`, `Flags = 0x04` `END_HEADERS`):
     - `:status` -> `"200"`
     - `content-type` -> (e.g. `"text/html"`)
     - `content-length` -> (file size in bytes)
     - `server` -> `"bserve/1.0"`
   - Server sends `DATA` (`0x00`, `Flags = 0x01` `END_STREAM`):
     - Payload contains the exact raw file bytes.
2. **File Not Found (404):**
   - Server sends `HEADERS` (`0x01`, `Flags = 0x04` `END_HEADERS`):
     - `:status` -> `"404"`
     - `content-type` -> `"text/plain"`
     - `content-length` -> length of error message
   - Server sends `DATA` (`0x00`, `Flags = 0x01` `END_STREAM`):
     - Payload: `"404 Not Found\n"`
3. **Malformed Request (400):**
   - If frame length is invalid, header count is out of bounds, or required pseudo-headers are missing:
   - Server returns 400 Bad Request and may reset the stream.

### 5.3 Keep-Alive & Connection Retention
After the `END_STREAM` frame is transmitted, the TCP connection **MUST remain open**. Either party may issue additional requests or responses on new streams.

---

## 6. Forward Compatibility (Version 2 Readiness)

### The Mandatory Unknown Frame Rule
> **A receiver meeting a frame type it does not know MUST skip it cleanly.**

When reading from the socket:
1. The receiver reads the 9-byte header.
2. The receiver extracts `Length` (first 24 bits).
3. If `Type` is not supported (e.g., `0x06`, `0x20`, `0xFF`):
   - The receiver performs a blocking read of exactly `Length` bytes from the socket.
   - The receiver discards those bytes entirely.
   - The receiver continues reading the next frame on the connection.
4. No error is raised, and the connection is **not closed**.

---

## 7. Exit Codes & Error Handling

- **Client (`bcurl`):**
  - Exit code `0` on 2xx and 3xx responses.
  - Exit code non-zero (e.g., status code modulo 256, or code `4` for 4xx and `5` for 5xx) whenever the server returns a 4xx or 5xx status.
- **Verbose Mode (`-v`):**
  - When invoked with `-v`, `bcurl` logs every frame sent and received to standard error (`stderr`), displaying:
    - Direction (`> ` for outgoing, `< ` for incoming)
    - Parsed header breakdown (Length, Type, Flags, Stream ID)
    - Full formatted hex + ASCII dump of the raw frame bytes.
