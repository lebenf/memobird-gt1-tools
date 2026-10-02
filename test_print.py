#!/usr/bin/env python3
"""Test standalone stampa immagine con output verboso."""
import sys, io, time, socket, struct
sys.path.insert(0, "/home/benfe/Documenti/workspace/memobird/memobird-gt1-mcp")
from memobird_driver import MemobirdGT1, tlv, le16, make_frame, DOT_WIDTH
from PIL import Image

MAC = "00:15:83:41:D3:9C"

def print_image_verbose(mac=MAC):
    # Immagine semplice: strisce orizzontali 384x96
    img = Image.new('L', (384, 96), 255)
    for y in range(96):
        if (y // 12) % 2 == 0:
            for x in range(384):
                img.putpixel((x, y), 0)

    img1 = img.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
    img1 = img1.transpose(Image.FLIP_TOP_BOTTOM)
    buf = io.BytesIO()
    img1.save(buf, format="BMP")
    bmp_bytes = buf.getvalue()
    print(f"BMP size: {len(bmp_bytes)} bytes")

    printer = MemobirdGT1(mac=mac, timeout=15.0)
    printer.connect()
    print("Connesso")

    # warmup
    printer.sock.send(b"\x00" * 1024)
    time.sleep(0.15)
    printer.sock.send(b"\x00" * 1024)
    time.sleep(0.15)
    print("Warmup inviato")

    CHUNK_SIZE = 1024
    total_pkts = (len(bmp_bytes) + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"Invio {total_pkts} pacchetti...")

    printer.sock.settimeout(5.0)
    for i in range(total_pkts):
        chunk = bmp_bytes[i*CHUNK_SIZE:(i+1)*CHUNK_SIZE]
        payload = tlv(11, le16(total_pkts)) + tlv(12, le16(i+1)) + tlv(8, chunk)
        frame = make_frame(cmd=4, payload=payload)
        printer.sock.send(frame)
        print(f"  Pacchetto {i+1}/{total_pkts} ({len(chunk)} bytes) inviato")
        time.sleep(0.1)

    print("Tutti i pacchetti inviati. Attendo 1.5s...")
    time.sleep(1.5)

    # feed carta
    feed_payload = (tlv(11, le16(1)) + tlv(12, le16(1)) +
                    tlv(13, bytes([0])) + tlv(17, bytes([0])) +
                    tlv(16, bytes([0])) + tlv(7, b"\n\n\n"))
    printer.sock.send(make_frame(cmd=4, payload=feed_payload))
    print("Feed carta inviato")

    try:
        ack = printer.sock.recv(512)
        print(f"ACK ricevuto: {len(ack)} bytes -> {ack.hex()}")
    except Exception as e:
        print(f"Nessun ACK: {e}")

    printer.close()
    print("Fine.")

if __name__ == "__main__":
    print_image_verbose()
