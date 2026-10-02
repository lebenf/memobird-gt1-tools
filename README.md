# Memobird GT1 Tools 🖨️

Open-source driver + MCP Server for the **Memobird GT1** thermal printer — no official app, no cloud, no account required.

Connects directly to the device via classic Bluetooth SPP, letting Claude Code, Cursor, or any MCP client print receipts, to-do lists, images, and more. Also includes a standalone GUI tool for quick image printing.

> Protocol reverse-engineered from the official Android SDK (`cn.memobird.gtx`). See [Protocol Details](#protocol-details) below.

---

## ✨ Features

- 🚫 **Zero official dependencies** — no app, no account, no internet. Pure local Bluetooth.
- 🔌 **Standard MCP tools** — `get_device_status` / `print_text` / `print_image`, usable from any MCP client.
- 🖼️ **Flexible image printing** — local path or HTTP/HTTPS URL, auto-scaled to 384 dots with Floyd–Steinberg dithering.
- 🖥️ **GUI app** — `print_gui.py` for drag-and-click image printing with live preview.
- 🧩 **Standalone library** — use `memobird_driver.py` directly in your own Python code.
- 🔧 **Single-file driver** — no third-party Bluetooth dependencies; only Pillow required.

## 🖥️ System Requirements

| | |
|---|---|
| OS | **Linux** — uses `socket.AF_BLUETOOTH` (kernel RFCOMM support required) |
| Bluetooth | Classic Bluetooth adapter (BlueZ 5.x), device already paired |
| Python | 3.8+ |
| Hardware | Memobird GT1 (other models untested, protocol may be compatible) |

> ⚠️ Linux only. Windows/macOS use a different RFCOMM interface and are not currently supported.

## 📦 Installation

```bash
git clone https://github.com/lebenf/memobird-gt1-tools.git
cd memobird-gt1-tools
python3 -m venv .venv
source .venv/bin/activate
pip install "mcp<2" Pillow PyQt6
```

> **Note:** `mcp>=2` renames `FastMCP` and breaks the MCP server. Pin `mcp<2`.

## 📡 Finding Your Bluetooth MAC Address

```bash
bluetoothctl scan on
# Look for "MEMOBIRD GT1" in the output and note its MAC address
bluetoothctl scan off

# Or list already-paired devices:
bluetoothctl devices
```

## 🚀 Standalone Usage

```python
from memobird_driver import MemobirdGT1

printer = MemobirdGT1(mac="00:15:83:XX:XX:XX")  # replace with your MAC

# Print text
with printer:
    printer.print_text("Hello from Python!\nDirect Bluetooth print.")

# Print image (local path, PIL Image, or bytes)
with printer:
    printer.print_image("photo.png")
    printer.print_image("https://example.com/image.jpg")
```

## 🖥️ GUI App

Launch the graphical image printer:

```bash
python print_gui.py
```

- Browse and preview any image file
- Toggle Floyd–Steinberg dithering (recommended for photos)
- One-click print; status feedback in real time

## 🔗 MCP Integration

### Claude Code (global, all projects)

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "memobird-gt1": {
      "command": "/path/to/.venv/bin/python",
      "args": ["/path/to/memobird_mcp.py"],
      "env": {
        "MEMOBIRD_MAC": "00:15:83:XX:XX:XX"
      }
    }
  }
}
```

### Claude Desktop / Cursor

```json
{
  "mcpServers": {
    "memobird-gt1": {
      "command": "/path/to/.venv/bin/python",
      "args": ["/path/to/memobird_mcp.py"],
      "env": { "MEMOBIRD_MAC": "00:15:83:XX:XX:XX" }
    }
  }
}
```

### Available MCP Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `get_device_status` | `mac` (optional) | Check connection and read serial number |
| `print_text` | `content`, `bold`, `underline`, `mac` | Print a text receipt |
| `print_image` | `image_path_or_url`, `dither`, `mac` | Print a local file or HTTP/HTTPS image |

## 📐 Protocol Details

Reverse-engineered from the official Memobird GT1 Android SDK:

- **Physical layer**: Classic Bluetooth SPP (RFCOMM), channel 1.
- **Frame format**:
  ```
  0xAA | len(2B, LE) | cmd(1B) | payload(TLV sequence) | checksum(1B)
  ```
  Checksum: `(256 - sum(body) & 0xFF) & 0xFF`
- **Commands**:
  - `cmd 0x01` — Handshake / status query; returns serial number and firmware info.
  - `cmd 0x04` — Print channel; payload is a sequence of TLV blocks.
- **Key TLV tags**:
  - `Tag 11` (2B) — Total packet count for this job
  - `Tag 12` (2B) — Current packet index
  - `Tag 7` — GBK-encoded text data
  - `Tag 8` — 1-bit monochrome BMP image chunk (1024 bytes per packet)
  - `Tag 13` / `Tag 17` / `Tag 16` — Bold / underline / font size flags
- **Warmup sequence**: Two 1024-byte zero-padding bursts must be sent before each print job. This is a firmware protection requirement.
- **Image orientation quirk**: The official `BMPFile.createBMPArray` produces a non-standard BMP with a positive `biHeight` but top-down pixel row order. Standard PIL saves bottom-up. The driver applies `FLIP_TOP_BOTTOM` before saving so the file bytes match what the firmware expects — without this, images print upside-down.
- **Burst mode**: All packets are sent without waiting for per-packet ACK. Waiting for per-packet ACK causes a ~3-second timeout per packet, dragging multi-packet jobs to tens of seconds and triggering a firmware timeout that results in no paper feed.
- **Timing**: Image printing requires slightly longer inter-packet delays (≥100 ms) and a longer post-transmission pause (≥1.5 s) compared to the original SDK defaults. The driver in this repo has been tuned to reliable values.

## ⚠️ Known Limitations

- The printer auto-sleeps after inactivity (Bluetooth disconnects with `Host is down`). Press the physical button to wake it before connecting.
- Linux + BlueZ only. Windows/macOS require RFCOMM layer adaptation.
- Serial number parsing relies on fixed response packet offsets; different firmware versions may differ (does not affect printing).

## 📄 License

[MIT](LICENSE)
