#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Client GraphQL subscription tối giản (chỉ thư viện chuẩn) cho smoke bản đồ realtime (#60).

Mở WebSocket tới ws://localhost:9080/graphql (qua APISIX) với subprotocol graphql-transport-ws, gửi
connection_init mang JWT trong payload.headers (giống web điều phối: trình duyệt không gửi được header
khi mở WebSocket), subscribe rồi in MỘT dòng JSON kết quả và thoát:
  {"ket_noi": "loi_http", "ma": 403}                          bắt tay HTTP bị từ chối (WAF, rate limit)
  {"ket_noi": "tu_choi", "ma": 4400, "ly_do": "..."}          Hasura đóng kết nối (JWT sai, vai không hợp lệ)
  {"ket_noi": "ok", "loi": ["..."], "ma_loi": ["..."]}         kết nối được nhưng subscription bị từ chối
  {"ket_noi": "ok", "so_tin": N, "truong": [...]}              kết quả đầu tiên (không có --cho-moi)
  {"ket_noi": "ok", "so_tin": N, "truong": [...], "moi": {...}, "luc_nhan": t}   tin mới đầu tiên
  {"ket_noi": "ok", "so_tin": N, "moi": null}                  hết giờ, không thấy tin mới

  graphql-ws.py <url> [--vai VAI] [--query Q] [--cho-moi] [--giay N] [--san-sang FILE]
--cho-moi: sau kết quả đầu tiên, chờ một id chưa có trong kết quả đầu (tin vừa tạo) trong N giây.
--san-sang: ghi file này khi đã nhận kết quả đầu tiên (smoke đợi file rồi mới tạo tin thử).
JWT đọc từ biến môi trường GRAPHQL_TOKEN (không lộ trên dòng lệnh); rỗng thì không gửi payload.
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

QUERY_BAN_DO = ("subscription BanDoTin($gioiHan: Int!) { incidents(order_by: {created_at: desc}, limit: $gioiHan)"
                " { id location urgency status created_at } }")


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
         f"Sec-WebSocket-Key: {khoa}\r\nSec-WebSocket-Version: 13\r\n"
         f"Sec-WebSocket-Protocol: graphql-transport-ws\r\nOrigin: {origin}\r\n"
         "User-Agent: dxos-smoke-ban-do\r\n\r\n").encode()
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


def gui_json(s: socket.socket, m: dict) -> None:
    gui(s, json.dumps(m).encode())


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
    ap.add_argument("--vai", default="")
    ap.add_argument("--query", default=QUERY_BAN_DO)
    ap.add_argument("--origin", default="http://localhost:9080")
    ap.add_argument("--cho-moi", action="store_true")
    ap.add_argument("--giay", type=float, default=10)
    ap.add_argument("--san-sang", default="")
    a = ap.parse_args()
    token = os.environ.get("GRAPHQL_TOKEN", "")

    try:
        s, ma = bat_tay(a.url, a.origin, a.giay)
    except OSError as e:
        return in_ket_qua({"ket_noi": "loi_mang", "ly_do": str(e)})
    if ma != 101:
        return in_ket_qua({"ket_noi": "loi_http", "ma": ma})
    init: dict = {"type": "connection_init"}
    if token:
        headers = {"Authorization": f"Bearer {token}"}
        if a.vai:
            headers["X-Hasura-Role"] = a.vai
        init["payload"] = {"headers": headers}
    gui_json(s, init)

    het = time.monotonic() + a.giay
    kq: dict = {}
    dau_tien: set[str] | None = None
    try:
        while time.monotonic() < het:
            s.settimeout(max(0.1, het - time.monotonic()))
            opcode, du_lieu = doc_frame(s)
            if opcode == 8:  # close: 2 byte mã + lý do
                ma_dong = struct.unpack("!H", du_lieu[:2])[0] if len(du_lieu) >= 2 else 0
                return in_ket_qua({**kq, "ket_noi": "tu_choi", "ma": ma_dong,
                                   "ly_do": du_lieu[2:].decode(errors="replace")})
            if opcode == 9:
                gui(s, du_lieu, opcode=10)
                continue
            if opcode != 1:
                continue
            m = json.loads(du_lieu)
            loai = m.get("type")
            if loai == "ping":
                gui_json(s, {"type": "pong"})
            elif loai == "connection_ack":
                kq = {"ket_noi": "ok"}
                gui_json(s, {"id": "1", "type": "subscribe",
                             "payload": {"query": a.query, "variables": {"gioiHan": 500}}})
            elif loai == "error":
                loi = m.get("payload") or []
                return in_ket_qua({**kq, "loi": [x.get("message", "") for x in loi],
                                   "ma_loi": [(x.get("extensions") or {}).get("code", "") for x in loi]})
            elif loai == "next":
                p = m.get("payload") or {}
                if p.get("errors"):
                    return in_ket_qua({**kq, "loi": [x.get("message", "") for x in p["errors"]],
                                       "ma_loi": [(x.get("extensions") or {}).get("code", "") for x in p["errors"]]})
                ds = (p.get("data") or {}).get("incidents") or []
                ids = {t["id"] for t in ds}
                kq["so_tin"] = len(ds)
                kq["truong"] = sorted({k for t in ds for k in t})
                if dau_tien is None:
                    dau_tien = ids
                    kq["ids"] = sorted(ids)
                    if a.san_sang:
                        with open(a.san_sang, "w", encoding="utf-8") as f:
                            f.write("ok\n")
                    if not a.cho_moi:
                        return in_ket_qua(kq)
                    continue
                moi = [t for t in ds if t["id"] not in dau_tien]
                if moi:
                    kq.pop("ids", None)
                    return in_ket_qua({**kq, "moi": moi[0], "luc_nhan": time.time()})
            elif loai == "complete":
                return in_ket_qua({**kq, "ket_noi": "complete"})
    except (TimeoutError, socket.timeout):
        pass
    except ConnectionError as e:
        kq.pop("ids", None)
        return in_ket_qua({**kq, "ket_noi": kq.get("ket_noi", "dong"), "ly_do": str(e)})
    finally:
        s.close()
    kq.pop("ids", None)
    return in_ket_qua({**kq, "ket_noi": kq.get("ket_noi", "het_gio"), "moi": None})


if __name__ == "__main__":
    sys.exit(main())
