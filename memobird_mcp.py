#!/usr/bin/env python3
"""
Memobird GT1 MCP Server
为咕咕机 GT1 热敏打印机提供标准 MCP 协议工具支持。
"""

import os
import sys
import urllib.request
from typing import Optional

# 引入同级驱动
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from memobird_driver import MemobirdGT1

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    # 兼容备用方案：简易 JSON-RPC stdio
    FastMCP = None

mcp = FastMCP("MemobirdGT1") if FastMCP else None

def get_printer(mac: Optional[str] = None):
    target_mac = mac or os.environ.get("MEMOBIRD_MAC", "00:15:83:41:F8:B2")
    return MemobirdGT1(mac=target_mac)

if mcp:
    @mcp.tool()
    def get_device_status(mac: Optional[str] = None) -> str:
        """获取咕咕机GT1的连接状态及设备序列号"""
        try:
            with get_printer(mac) as printer:
                status = printer.get_status()
                return f"咕咕机 GT1 连接正常！序列号: {status.get('sn', '未知')}, MAC: {status.get('mac')}"
        except Exception as e:
            return f"获取设备状态失败: {str(e)}"

    @mcp.tool()
    def print_text(content: str, bold: bool = False, underline: bool = False, mac: Optional[str] = None) -> str:
        """
        在咕咕机GT1上打印指定的纯文本小票/纸条。
        :param content: 需要打印的文本内容
        :param bold: 是否加粗
        :param underline: 是否带下划线
        """
        try:
            with get_printer(mac) as printer:
                printer.print_text(content, bold=bold, underline=underline)
                return "文本内容已成功发送并打印！"
        except Exception as e:
            return f"打印文本失败: {str(e)}"

    @mcp.tool()
    def print_image(image_path_or_url: str, dither: bool = True, mac: Optional[str] = None) -> str:
        """
        在咕咕机GT1上打印图片（支持本地文件路径或网络URL，自动处理灰度和Floyd-Steinberg抖动二值化）。
        :param image_path_or_url: 图片本地路径或 HTTP/HTTPS 链接
        :param dither: 是否开启误差扩散抖动算法以保留图像层次细节（默认 True）
        """
        try:
            if image_path_or_url.startswith("http://") or image_path_or_url.startswith("https://"):
                req = urllib.request.Request(image_path_or_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    img_data = resp.read()
            else:
                with open(image_path_or_url, "rb") as f:
                    img_data = f.read()

            with get_printer(mac) as printer:
                printer.print_image(img_data, dither=dither)
                return "图片已成功转换点阵并打印完成！"
        except Exception as e:
            return f"打印图片失败: {str(e)}"

if __name__ == "__main__":
    if mcp:
        mcp.run()
    else:
        print("FastMCP not installed in this environment. Run with python -m tools.memobird_gt1.memobird_mcp after installing mcp.")
