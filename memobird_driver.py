import io
import time
import socket
from typing import Optional, Tuple, Dict, Any
from PIL import Image

DEFAULT_MAC = "00:15:83:41:F8:B2"
DEFAULT_PORT = 1
DOT_WIDTH = 384  # GT1 打印头物理宽度：384 点阵

def le16(n: int) -> bytes:
    return bytes([n & 0xFF, (n >> 8) & 0xFF])

def tlv(tag: int, val: bytes) -> bytes:
    return bytes([tag]) + le16(len(val)) + val

def make_frame(cmd: int, payload: bytes) -> bytes:
    cmd_bytes = bytes([cmd])
    total_len = len(cmd_bytes) + len(payload)
    len_bytes = le16(total_len)
    body = b"\xAA" + len_bytes + cmd_bytes + payload
    chk = (256 - (sum(body) & 0xFF)) & 0xFF
    return body + bytes([chk])

class MemobirdGT1:
    def __init__(self, mac: str = DEFAULT_MAC, port: int = DEFAULT_PORT, timeout: float = 10.0):
        self.mac = mac
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None

    def connect(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self.sock.settimeout(self.timeout)
        self.sock.connect((self.mac, self.port))
        # 握手命令
        self.sock.send(make_frame(cmd=1, payload=b""))
        try:
            _ = self.sock.recv(1024)
        except Exception:
            pass

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_status(self) -> Dict[str, Any]:
        self.sock.send(make_frame(cmd=1, payload=b""))
        resp = self.sock.recv(1024)
        sn = ""
        if len(resp) >= 50:
            try:
                # 序列号位于 offset 35 附近
                raw_sn = resp[35:55].split(b'\x00')[0]
                sn = raw_sn.decode('ascii', errors='ignore')
            except Exception:
                pass
        return {
            "connected": True,
            "mac": self.mac,
            "sn": sn,
            "raw_resp": resp.hex()
        }

    def _warmup(self):
        # 官方驱动固件保护预热序列
        self.sock.send(b"\x00" * 1024)
        time.sleep(0.15)
        self.sock.send(b"\x00" * 1024)
        time.sleep(0.15)

    def print_text(self, text: str, bold: bool = False, underline: bool = False, font_size: int = 0) -> bool:
        if not text.endswith("\n"):
            text += "\n"
        self._warmup()
        gbk_bytes = text.encode("gbk", errors="replace")
        
        # 分片如果太长每段 300 字节
        CHUNK_LIMIT = 300
        chunks = [gbk_bytes[i:i+CHUNK_LIMIT] for i in range(0, len(gbk_bytes), CHUNK_LIMIT)]
        if not chunks:
            chunks = [b"\n"]
        total = len(chunks)
        
        for idx, chunk in enumerate(chunks, 1):
            tlv_total = tlv(11, le16(total))
            tlv_idx = tlv(12, le16(idx))
            tlv_bold = tlv(13, bytes([1 if bold else 0]))
            tlv_ul = tlv(17, bytes([1 if underline else 0]))
            tlv_size = tlv(16, bytes([font_size]))
            tlv_text = tlv(7, chunk)
            payload = tlv_total + tlv_idx + tlv_bold + tlv_ul + tlv_size + tlv_text
            self.sock.send(make_frame(cmd=4, payload=payload))
            time.sleep(0.05)
            
        try:
            ack = self.sock.recv(512)
            return len(ack) > 0
        except Exception:
            return True

    def print_image(self, image_input, dither: bool = True, feed_lines: int = 3) -> bool:
        """
        image_input: PIL.Image 实例、文件路径 (str) 或 二进制流 (bytes)
        """
        if isinstance(image_input, str):
            img = Image.open(image_input)
        elif isinstance(image_input, bytes):
            img = Image.open(io.BytesIO(image_input))
        elif isinstance(image_input, Image.Image):
            img = image_input
        else:
            raise ValueError("Unsupported image input type")

        # 转换为单色点阵图（宽度固定为 384 点）
        if img.mode != 'L':
            img = img.convert('L')

        # 按比例缩放到宽 384
        w, h = img.size
        new_w = DOT_WIDTH
        new_h = int(h * (new_w / w))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # 二值化（抖动算法保留灰度层次细节）
        if dither:
            img = img.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
        else:
            img = img.point(lambda x: 0 if x < 128 else 255, '1')

        # 与官方 SDK 对齐：BMPFile.createBMPArray 生成的是 biHeight 为正、
        # 像素行序 top-down 的非标准 BMP，打印机固件即按 top-down 解析数据。
        # PIL 默认输出 bottom-up 行序，先垂直翻转图像再以标准格式保存，
        # 最终文件数据行序即变为 top-down，与官方 BMP 完全一致。
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        bmp_io = io.BytesIO()
        img.save(bmp_io, format="BMP")
        bmp_bytes = bmp_io.getvalue()

        self._warmup()

        CHUNK_SIZE = 1024
        total_pkts = (len(bmp_bytes) + CHUNK_SIZE - 1) // CHUNK_SIZE
        tlv_total = tlv(11, le16(total_pkts))

        self.sock.settimeout(5.0)
        for i in range(total_pkts):
            pkt_no = i + 1
            chunk = bmp_bytes[i * CHUNK_SIZE : (i + 1) * CHUNK_SIZE]
            tlv_idx = tlv(12, le16(pkt_no))
            tlv_img = tlv(8, chunk)
            payload = tlv_total + tlv_idx + tlv_img
            frame = make_frame(cmd=4, payload=payload)
            sent = False
            for attempt in range(3):
                try:
                    self.sock.send(frame)
                    sent = True
                    break
                except Exception:
                    time.sleep(0.8)
                    try:
                        self.connect()
                    except Exception:
                        time.sleep(1.0)
            if not sent:
                raise RuntimeError(f"packet {pkt_no}/{total_pkts} 发送失败")
            # 连发模式: 固件缓冲区足够, 不逐包等 ACK, 避免拖慢任务触发超时
            time.sleep(0.10)

        # 走纸
        if feed_lines > 0:
            time.sleep(1.5)
            feed_txt = "\n" * feed_lines
            feed_payload = tlv(11, le16(1)) + tlv(12, le16(1)) + tlv(13, bytes([0])) + tlv(17, bytes([0])) + tlv(16, bytes([0])) + tlv(7, feed_txt.encode('gbk'))
            self.sock.send(make_frame(cmd=4, payload=feed_payload))

        try:
            ack = self.sock.recv(512)
            return len(ack) > 0
        except Exception:
            return True
