# Annotated Hexdump of One Complete Request & Response
**Protocol:** Binary HTTP (BHTTP/1.0)  
**Exchange:** `bcurl -v localhost:9000/hello.txt`  
**Payload File Content:** `Hello, Binary World! BHTTP protocol is functioning properly.\n` (61 bytes)

---

## 1. Request Frame (Client -> Server)

The client issues a single **HEADERS** frame initiating Stream 1 with flags `END_STREAM | END_HEADERS` (`0x05`).

### 1.1 Complete Wire Hexdump (65 bytes total: 9-byte header + 56-byte payload)

```
Offset  00 01 02 03 04 05 06 07  08 09 0A 0B 0C 0D 0E 0F  ASCII
--------------------------------------------------------------------------------
0000:   00 00 38 01 05 00 00 00  01 00 05 01 00 03 47 45  |..8...........GE|
0010:   54 02 00 0a 2f 68 65 6c  6c 6f 2e 74 78 74 04 00  |T.../hello.txt..|
0020:   0e 6c 6f 63 61 6c 68 6f  73 74 3a 39 30 30 30 05  |.localhost:9000.|
0030:   00 09 62 63 75 72 6c 2f  31 2e 30 08 00 03 2a 2f  |..bcurl/1.0...*/|
0040:   2a                                                |*|
```

### 1.2 Byte-by-Byte Field Annotation

#### A. 9-Byte Fixed Frame Header
| Byte Offsets | Hex Bytes | Field Name | Value / Meaning |
|---|---|---|---|
| `0000 - 0002` | `00 00 38` | **Length (24 bits)** | `0x000038` = **56 bytes** payload |
| `0003` | `01` | **Type (8 bits)** | `0x01` = **FRAME_HEADERS** |
| `0004` | `05` | **Flags (8 bits)** | `0x05` = `FLAG_END_STREAM (0x01) \| FLAG_END_HEADERS (0x04)` |
| `0005 - 0008` | `00 00 00 01` | **Stream ID (31 bits + 1b R)** | `1` (First client-initiated stream, odd integer) |

#### B. 56-Byte Payload (HPACK-Lite Header Block)
| Byte Offsets | Hex Bytes | Field Name | Decoded Meaning |
|---|---|---|---|
| `0009 - 000A` | `00 05` | **Header Count (16 bits)** | 5 headers follow |
| **Header 1: `:method`** | | | |
| `000B` | `01` | Header Name Index | Static Table index `1` (`:method`) |
| `000C - 000D` | `00 03` | Value Length | 3 bytes |
| `000E - 0010` | `47 45 54` | Value Bytes | ASCII `"GET"` |
| **Header 2: `:path`** | | | |
| `0011` | `02` | Header Name Index | Static Table index `2` (`:path`) |
| `0012 - 0013` | `00 0A` | Value Length | 10 bytes |
| `0014 - 001D` | `2f 68 65 6c 6c 6f 2e 74 78 74` | Value Bytes | ASCII `"/hello.txt"` |
| **Header 3: `host`** | | | |
| `001E` | `04` | Header Name Index | Static Table index `4` (`host`) |
| `001F - 0020` | `00 0E` | Value Length | 14 bytes |
| `0021 - 002E` | `6c 6f 63 61 6c 68 6f 73 74 3a 39 30 30 30` | Value Bytes | ASCII `"localhost:9000"` |
| **Header 4: `user-agent`** | | | |
| `002F` | `05` | Header Name Index | Static Table index `5` (`user-agent`) |
| `0030 - 0031` | `00 09` | Value Length | 9 bytes |
| `0032 - 003A` | `62 63 75 72 6c 2f 31 2e 30` | Value Bytes | ASCII `"bcurl/1.0"` |
| **Header 5: `accept`** | | | |
| `003B` | `08` | Header Name Index | Static Table index `8` (`accept`) |
| `003C - 003D` | `00 03` | Value Length | 3 bytes |
| `003E - 0040` | `2a 2f 2a` | Value Bytes | ASCII `"*/*"` |

---

## 2. Response Frame 1: HEADERS (Server -> Client)

The server responds on Stream 1 with metadata: status code 200 and MIME headers.

### 2.1 Complete Wire Hexdump (48 bytes total: 9-byte header + 39-byte payload)

```
Offset  00 01 02 03 04 05 06 07  08 09 0A 0B 0C 0D 0E 0F  ASCII
--------------------------------------------------------------------------------
0000:   00 00 27 01 04 00 00 00  01 00 04 03 00 03 32 30  |..'...........20|
0010:   30 09 00 0a 62 73 65 72  76 65 2f 31 2e 30 06 00  |0...bserve/1.0..|
0020:   0a 74 65 78 74 2f 70 6c  61 69 6e 07 00 02 36 31  |.text/plain...61|
```

### 2.2 Byte-by-Byte Field Annotation

#### A. 9-Byte Fixed Frame Header
| Byte Offsets | Hex Bytes | Field Name | Value / Meaning |
|---|---|---|---|
| `0000 - 0002` | `00 00 27` | **Length (24 bits)** | `0x000027` = **39 bytes** payload |
| `0003` | `01` | **Type (8 bits)** | `0x01` = **FRAME_HEADERS** |
| `0004` | `04` | **Flags (8 bits)** | `0x04` = `FLAG_END_HEADERS` (stream does NOT end; DATA frame follows) |
| `0005 - 0008` | `00 00 00 01` | **Stream ID (31 bits + 1b R)** | `1` (Corresponds to request Stream 1) |

#### B. 39-Byte Payload (HPACK-Lite Header Block)
| Byte Offsets | Hex Bytes | Field Name | Decoded Meaning |
|---|---|---|---|
| `0009 - 000A` | `00 04` | **Header Count (16 bits)** | 4 headers follow |
| **Header 1: `:status`** | | | |
| `000B` | `03` | Header Name Index | Static Table index `3` (`:status`) |
| `000C - 000D` | `00 03` | Value Length | 3 bytes |
| `000E - 0010` | `32 30 30` | Value Bytes | ASCII `"200"` |
| **Header 2: `server`** | | | |
| `0011` | `09` | Header Name Index | Static Table index `9` (`server`) |
| `0012 - 0013` | `00 0A` | Value Length | 10 bytes |
| `0014 - 001D` | `62 73 65 72 76 65 2f 31 2e 30` | Value Bytes | ASCII `"bserve/1.0"` |
| **Header 3: `content-type`** | | | |
| `001E` | `06` | Header Name Index | Static Table index `6` (`content-type`) |
| `001F - 0020` | `00 0A` | Value Length | 10 bytes |
| `0021 - 002A` | `74 65 78 74 2f 70 6c 61 69 6e` | Value Bytes | ASCII `"text/plain"` |
| **Header 4: `content-length`** | | | |
| `002B` | `07` | Header Name Index | Static Table index `7` (`content-length`) |
| `002C - 002D` | `00 02` | Value Length | 2 bytes |
| `002E - 002F` | `36 31` | Value Bytes | ASCII `"61"` |

---

## 3. Response Frame 2: DATA (Server -> Client)

Carries raw file contents for Stream 1, closing the stream via `END_STREAM`.

### 3.1 Complete Wire Hexdump (70 bytes total: 9-byte header + 61-byte payload)

```
Offset  00 01 02 03 04 05 06 07  08 09 0A 0B 0C 0D 0E 0F  ASCII
--------------------------------------------------------------------------------
0000:   00 00 3d 00 01 00 00 00  01 48 65 6c 6c 6f 2c 20  |..=......Hello, |
0010:   42 69 6e 61 72 79 20 57  6f 72 6c 64 21 20 42 48  |Binary World! BH|
0020:   54 54 50 20 70 72 6f 74  6f 63 6f 6c 20 69 73 20  |TTP protocol is |
0030:   66 75 6e 63 74 69 6f 6e  69 6e 67 20 70 72 6f 70  |functioning prop|
0040:   65 72 6c 79 2e 0a                                 |erly..|
```

### 3.2 Byte-by-Byte Field Annotation

#### A. 9-Byte Fixed Frame Header
| Byte Offsets | Hex Bytes | Field Name | Value / Meaning |
|---|---|---|---|
| `0000 - 0002` | `00 00 3d` | **Length (24 bits)** | `0x00003d` = **61 bytes** payload |
| `0003` | `00` | **Type (8 bits)** | `0x00` = **FRAME_DATA** |
| `0004` | `01` | **Flags (8 bits)** | `0x01` = `FLAG_END_STREAM` (terminates response for Stream 1) |
| `0005 - 0008` | `00 00 00 01` | **Stream ID (31 bits + 1b R)** | `1` (Stream 1) |

#### B. 61-Byte Payload (Raw File Content)
| Byte Offsets | Hex Bytes | Field Name | Decoded Meaning |
|---|---|---|---|
| `0009 - 0045` | `48 65 6c 6c 6f 2c 20 ... 6c 79 2e 0a` | **Body Bytes** | Exact content of `hello.txt`: `"Hello, Binary World! BHTTP protocol is functioning properly.\n"` |
