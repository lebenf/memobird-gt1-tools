# Memobird GT1 MCP Server 🖨️

无需官方 App、无需云服务的**咕咕机 GT1 热敏打印机**开源驱动 + MCP Server。

通过经典蓝牙 SPP 协议直连设备，让你的 Claude / Cursor / 任何 MCP 客户端直接指挥打印机输出小票、待办清单、表情包图片等。

> 本项目完全基于对官方 Android SDK 的逆向分析，协议逆向细节见下文 [协议说明](#协议说明)。

---

## ✨ 特性

- 🚫 **零官方依赖**：不装官方 App、不注册账号、不联网，纯本地蓝牙直连。
- 🔌 **标准 MCP 工具**：`get_device_status` / `print_text` / `print_image`，任何 MCP 客户端可用。
- 🖼️ **任意图片打印**：本地文件或网络 URL 均可，自动等比缩放 + Floyd–Steinberg 误差扩散抖动，输出 384 点阵单色图。
- 🧩 **独立可用**：不接 MCP 也能当作普通 Python 库直接调用。
- 🔧 **单文件驱动**：`memobird_driver.py` 零第三方蓝牙依赖，仅需 Pillow。

## 🖥️ 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | **Linux**（驱动使用 `socket.AF_BLUETOOTH`，需要内核 RFCOMM 支持） |
| 蓝牙 | 经典蓝牙适配器（BlueZ 5.x），已配对/可发现目标设备 |
| Python | 3.8+ |
| 硬件 | 咕咕机 GT1（其他 Memobird 型号未测试，协议可能兼容） |

> ⚠️ 当前仅支持 Linux。Windows/macOS 的蓝牙 RFCOMM 接口与 Linux 不同，暂未适配。

## 📦 安装

```bash
git clone https://github.com/<your-account>/memobird-gt1-mcp.git
cd memobird-gt1-mcp
pip install -r requirements.txt
```

## 🚀 快速开始（独立使用）

```python
from memobird_driver import MemobirdGT1

# 默认 MAC 为开发者测试设备，请改成你自己的（见下文「获取蓝牙 MAC」）
printer = MemobirdGT1(mac="00:15:83:41:F8:B2")

# 打印文本
with printer:
    printer.print_text("你好，咕咕机！\n这是本地直连打印。")

# 打印图片（本地路径 / PIL 对象 / 二进制均可）
with printer:
    printer.print_image("hello.png")
    printer.print_image("https://example.com/pic.jpg")
```

## 🔗 MCP 集成

在 MCP 客户端配置中添加（以 Claude Desktop 为例）：

```json
{
  "mcpServers": {
    "memobird-gt1": {
      "command": "python",
      "args": ["/absolute/path/to/memobird_mcp.py"],
      "env": {
        "MEMOBIRD_MAC": "00:15:83:41:F8:B2"
      }
    }
  }
}
```

Cursor 则写入项目根目录 `.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "memobird-gt1": {
      "command": "python",
      "args": ["/absolute/path/to/memobird_mcp.py"],
      "env": { "MEMOBIRD_MAC": "00:15:83:41:F8:B2" }
    }
  }
}
```

配置后，即可让 AI 直接调用以下工具：

| 工具 | 参数 | 说明 |
|------|------|------|
| `get_device_status` | `mac`(可选) | 查询连接状态与设备序列号 |
| `print_text` | `content`, `bold`, `underline`, `mac` | 打印 GBK 编码文本小票 |
| `print_image` | `image_path_or_url`, `dither`, `mac` | 打印本地/网络图片，自动二值化 |

## 📡 获取蓝牙 MAC 地址

```bash
bluetoothctl scan on
# 观察输出，找到设备名 MEMOBIRD GT1 对应的 MAC
bluetoothctl scan off
```

也可用 `bluetoothctl devices` 列出已发现设备。

## 📐 协议说明

本项目逆向自咕咕机 GT1 官方 Android SDK（`cn.memobird.gtx`），核心结论：

- **物理层**：经典蓝牙 SPP（RFCOMM），默认 Channel 1。
- **帧格式**：
  ```
  | 0xAA | len(2B, LE) | cmd(1B) | payload(TLV 序列) | checksum(1B) |
  ```
  其中 `checksum = (256 - sum(body) & 0xFF) & 0xFF`。
- **主要指令**：
  - `cmd 0x01`：握手 / 状态查询，返回序列号与固件信息。
  - `cmd 0x04`：打印通道，payload 为 TLV 块。
- **关键 TLV Tag**：
  - `Tag 11`(2B)：本次任务总包数
  - `Tag 12`(2B)：当前包序号
  - `Tag 7`：GBK 编码文本
  - `Tag 8`：1-bit 单色 BMP 图像分片（每包 1024 字节）
  - `Tag 13`/`Tag 17`/`Tag 16`：加粗 / 下划线 / 字号
- **固件保护**：每次打印前需发送 2 次 1024 字节全零预热包。
- **图像方向坑**：官方 `BMPFile.createBMPArray` 生成的是 **biHeight 为正、像素按 top-down 行序**写入的非标准 BMP，而 PIL 默认输出 bottom-up。驱动在保存前对图像做 `FLIP_TOP_BOTTOM` 以对齐官方格式，否则打印结果会上下颠倒。
- **分包策略**：采用**连发模式**（发完所有包不等逐包 ACK）。实测「逐包等 ACK」会因每包 3 秒超时把多包任务拖到数十秒，触发固件超时导致不出纸。

## ⚠️ 已知限制

- 设备长时间无操作会**自动休眠关机**（蓝牙断开报 `Host is down`），需手动按键唤醒后重连。
- 仅支持 Linux + BlueZ；Windows/macOS 需自行适配 RFCOMM 层。
- 序列号解析依赖响应报文的固定偏移，不同固件版本可能偏移不同（不影响打印功能）。

## 📄 License

[MIT](LICENSE)
