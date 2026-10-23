#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Client WebSocket tối giản (chỉ thư viện chuẩn) cho smoke Centrifugo (#68, scripts/smoke-realtime.sh).

Mở WebSocket tới URL (vd ws://localhost:9080/realtime/websocket qua APISIX), gửi lệnh connect theo
giao thức JSON của Centrifugo, in MỘT dòng JSON kết quả rồi thoát:
  {"ket_noi": "ok", "kenh": [...]}                                  đã kết nối (kênh server-side)
  {"ket_noi": "ok", "kenh": [...], "nhan": {...}, "luc_nhan": t}   kèm sự kiện đầu tiên khớp --cho
  {"ket_noi": "tu_choi", "ma": 3500, "ly_do": "invalid token"}      bị từ chối (close frame/lỗi connect)
  {"ket_noi": "loi_http", "ma": 403}                                bắt tay HTTP bị từ chối (WAF, origin)

  realtime-ws.py <url> [--token T] [--origin O] [--cho LOAI:CHUOI] [--giay N]
--cho: chờ publication có data.loai == LOAI và chứa CHUOI trong JSON của data (trong N giây).
Token đọc từ biến môi trường REALTIME_TOKEN nếu không có --token (không lộ trên dòng lệnh).
"""

import argparse
import base64
import json
import os
import socket
import struct
import sys
import time
from urllib.parse import urlsplit


def bat_tay(url: str, origin: str, giay: float) -> tuple[socket.socket, int]:
    u = urlsplit(url)
    if u.scheme != "ws":
        raise SystemExit("chỉ hỗ trợ ws:// (smoke chạy trên máy dev)")
    port = u.port or 80
    s = socket.create_connection((u.hostname, port), timeout=giay)
    khoa = base64.b64encode(os.urandom(16)).decode()
    duong = (u.path or "/") + (f"?{u.query}" if u.query else "")
    s.sendall(
        (f"GET {duong} HTTP/1.1\r\nHost: {u.hostname}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
         f"Sec-WebSocket-Key: {khoa}\r\nSec-WebSocket-Version: 13\r\nOrigin: {origin}\r\n"
         "User-Agent: dxos-smoke-realtime\r\n\r\n").encode()
    )
    dau = b""
    while b"\r\n\r\n" not in dau:
        phan = s.recv(4096)
        if not phan:
            break
        dau += phan
    dong = dau.split(b"\r\n", 1)[0].decode(errors="replace")
    ma = int(dong.split()[1]) if len(dong.split()) > 1 else 0
    return s, ma


def gui(s: socket.socket, du_lieu: bytes, opcode: int = 1) -> None:
    mat_na = os.urandom(4)
    n = len(du_lieu)
    dau = bytes([0x80 | opcode])
    if n < 126:
        dau += bytes([0x80 | n])
    elif n < 65536:
        dau += bytes([0x80 | 126]) + struct.pack("!H", n)
    else:
        dau += bytes([0x80 | 127]) + struct.pack("!Q", n)
    s.sendall(dau + mat_na + bytes(b ^ mat_na[i % 4] for i, b in enumerate(du_lieu)))


def doc_du(s: socket.socket, n: int) -> bytes:
    b = b""
    while len(b) < n:
        phan = s.recv(n - len(b))
        if not phan:
            raise ConnectionError("đóng kết nối")
        b += phan
    return b


def doc_frame(s: socket.socket) -> tuple[int, bytes]:
    b0, b1 = doc_du(s, 2)
    n = b1 & 0x7F
    if n == 126:
        n = struct.unpack("!H", doc_du(s, 2))[0]
    elif n == 127:
        n = struct.unpack("!Q", doc_du(s, 8))[0]
    return b0 & 0x0F, doc_du(s, n)


def in_ket_qua(kq: dict) -> int:
    print(json.dumps(kq, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--token", default=os.environ.get("REALTIME_TOKEN", ""))
    ap.add_argument("--origin", default="http://localhost:9080")
    ap.add_argument("--cho", default="")
    ap.add_argument("--giay", type=float, default=10)
    a = ap.parse_args()

    try:
        s, ma = bat_tay(a.url, a.origin, a.giay)
    except OSError as e:
        return in_ket_qua({"ket_noi": "loi_mang", "ly_do": str(e)})
    if ma != 101:
        return in_ket_qua({"ket_noi": "loi_http", "ma": ma})
    lenh = {"id": 1, "connect": {"name": "dxos-smoke"}}
    if a.token:
        lenh["connect"]["token"] = a.token
    gui(s, json.dumps(lenh).encode())

    loai_cho, _, chuoi_cho = a.cho.partition(":")
    het = time.monotonic() + a.giay
    kq: dict = {}
    try:
        while time.monotonic() < het:
            s.settimeout(max(0.1, het - time.monotonic()))
            opcode, du_lieu = doc_frame(s)
            if opcode == 8:  # close: 2 byte mã + lý do
                ma_dong = struct.unpack("!H", du_lieu[:2])[0] if len(du_lieu) >= 2 else 0
                return in_ket_qua({"ket_noi": "tu_choi", "ma": ma_dong, "ly_do": du_lieu[2:].decode(errors="replace")})
            if opcode == 9:
                gui(s, du_lieu, opcode=10)
                continue
            if opcode != 1:
                continue
            # Một frame có thể chứa nhiều lệnh JSON, mỗi dòng một lệnh
            for dong in du_lieu.decode().splitlines():
                if not dong.strip():
                    continue
                m = json.loads(dong)
                if m == {}:  # ping của Centrifugo → pong
                    gui(s, b"{}")
                    continue
                if m.get("id") == 1:
                    if "error" in m:
                        return in_ket_qua({"ket_noi": "tu_choi", "ma": m["error"].get("code"),
                                           "ly_do": m["error"].get("message", "")})
                    kq = {"ket_noi": "ok", "kenh": sorted((m.get("connect") or {}).get("subs", {}))}
                    if not a.cho:
                        return in_ket_qua(kq)
                    continue
                pub = (m.get("push") or {}).get("pub")
                if pub is not None and kq:
                    data = pub.get("data") or {}
                    if data.get("loai") == loai_cho and chuoi_cho in json.dumps(data, ensure_ascii=False):
                        return in_ket_qua({**kq, "kenh_su_kien": m["push"].get("channel"), "nhan": data,
                                           "luc_nhan": time.time()})
    except (TimeoutError, socket.timeout):
        pass
    except ConnectionError as e:
        return in_ket_qua({**kq, "ket_noi": kq.get("ket_noi", "dong"), "ly_do": str(e)})
    finally:
        s.close()
    return in_ket_qua({**kq, "ket_noi": kq.get("ket_noi", "het_gio"), "nhan": None})


if __name__ == "__main__":
    sys.exit(main())
