# SPDX-License-Identifier: Apache-2.0
"""Phiếu nhập/xuất → sổ cái minh bạch của lõi (core/ledger, Tessera) → xác minh công khai (#28, D-007).

Luồng:
  1. API lập phiếu supply_movements (role cuu_tro_app), lấy dòng vừa ghi.
  2. `ban_ghi_chuan_hoa`: chỉ các cột không định danh (KHÔNG có created_by), mọi giá trị là chuỗi/null.
  3. `json_chuan_tac` + SHA-256 → gửi lá {type, ref = mã phiếu, sha256, attrs: chiều, số lượng, thời
     điểm} tới POST /ledger/entries (mạng nội bộ + token ghi của ứng dụng), lưu ledger_index và leaf hash.
  4. Trang công khai: đọc phiếu trong CSDL, băm lại, lấy lá + inclusion proof + checkpoint từ sổ cái,
     tự kiểm chữ ký checkpoint (Ed25519, định dạng note), kiểm lá chứa đúng SHA-256 và mã phiếu, leaf
     hash khớp CSDL, proof dẫn tới root của checkpoint (RFC 6962/9162). Lệch bất kỳ bước nào →
     "khong_khop" (bản ghi trong CSDL đã bị sửa, hoặc sổ cái bị sửa).

JSON chuẩn tắc trùng với core/ledger/leaf.CanonicalJSON (Go) để người ngoài kiểm lại bằng
core/ledger/cmd/ledger-verify: khóa sắp xếp, không khoảng trắng, UTF-8, U+2028/U+2029 viết \\u.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

LOAI_LA = "cuu-tro.phieu-kho"
PHIEN_BAN_BAN_GHI = "cuu-tro.phieu-kho/v1"

# Trạng thái xác minh trả cho trang công khai
DA_XAC_MINH = "da_xac_minh"
KHONG_KHOP = "khong_khop"
CHUA_GHI_SO = "chua_ghi_so"
KHONG_KIEM_DUOC = "khong_kiem_duoc"

# Dãy số dạng SĐT/CCCD Việt Nam (bắt đầu bằng 0, từ 9 chữ số): không cho vào ghi chú công khai
_SO_DINH_DANH = re.compile(r"(^|[^0-9])0[0-9]{8,}")


class LoiXacMinh(Exception):
    """Dữ liệu sổ cái không qua được một bước kiểm (chữ ký, định dạng, proof)."""


class LoiSoCai(Exception):
    """Không gọi được dịch vụ sổ cái (mạng, HTTP lỗi)."""


def co_so_dinh_danh(van_ban: str | None) -> bool:
    return bool(van_ban) and bool(_SO_DINH_DANH.search(van_ban))


# ---------------- Bản ghi chuẩn hóa ----------------

def _thoi_diem(dt: datetime) -> str:
    """UTC, luôn 6 chữ số micro giây: cùng một thời điểm luôn ra đúng một chuỗi."""
    if dt.tzinfo is None:
        raise ValueError("created_at phải có múi giờ")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _so_luong(q: Decimal | int | float | str) -> str:
    return f"{Decimal(str(q)):.2f}"


def ban_ghi_chuan_hoa(dong: dict[str, Any]) -> dict[str, str | None]:
    """Bản ghi công khai của một phiếu: đúng các cột không định danh, giá trị là chuỗi hoặc null."""
    return {
        "loai": PHIEN_BAN_BAN_GHI,
        "id": str(dong["id"]),
        "supply_id": str(dong["supply_id"]),
        "direction": str(dong["direction"]),
        "quantity": _so_luong(dong["quantity"]),
        "note": dong.get("note"),
        "shelter_id": str(dong["shelter_id"]) if dong.get("shelter_id") else None,
        "created_at": _thoi_diem(dong["created_at"]),
    }


def json_chuan_tac(ban_ghi: dict[str, str | None]) -> bytes:
    for k, v in ban_ghi.items():
        if not isinstance(k, str) or not (v is None or isinstance(v, str)):
            raise ValueError(f"trường {k!r}: bản ghi chuẩn hóa chỉ gồm chuỗi hoặc null")
    s = json.dumps(ban_ghi, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    # Như encoding/json của Go (core/ledger/leaf.CanonicalJSON)
    return s.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029").encode("utf-8")


def sha256_ban_ghi(ban_ghi: dict[str, str | None]) -> str:
    return hashlib.sha256(json_chuan_tac(ban_ghi)).hexdigest()


def la_cho_phieu(ban_ghi: dict[str, str | None]) -> dict[str, Any]:
    """Thân request POST /ledger/entries: không có dữ liệu cá nhân (D-007)."""
    return {
        "type": LOAI_LA,
        "ref": ban_ghi["id"],
        "sha256": sha256_ban_ghi(ban_ghi),
        "attrs": {"direction": ban_ghi["direction"], "quantity": ban_ghi["quantity"], "at": ban_ghi["created_at"]},
    }


# ---------------- Merkle RFC 6962 / 9162 ----------------

def leaf_hash(la: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + la).digest()


def _node(trai: bytes, phai: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + trai + phai).digest()


def kiem_inclusion(index: int, size: int, lh: bytes, proof: list[bytes], root: bytes) -> bool:
    """Kiểm inclusion proof theo RFC 9162 mục 2.1.3.2."""
    if index < 0 or index >= size:
        return False
    fn, sn, r = index, size - 1, lh
    for p in proof:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            r = _node(p, r)
            if not fn & 1:
                while not fn & 1 and fn != 0:
                    fn >>= 1
                    sn >>= 1
        else:
            r = _node(r, p)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == root


# ---------------- Checkpoint (note Ed25519) ----------------

@dataclass(frozen=True)
class KhoaCongKhai:
    ten: str
    hash4: bytes
    khoa: Ed25519PublicKey


def doc_khoa_cong_khai(vkey: str) -> KhoaCongKhai:
    """Đọc verifier key dạng note: <tên>+<8 hex>+<base64(0x01 || khóa 32 byte)>."""
    try:
        ten, h, b64 = vkey.strip().split("+", 2)
        raw = base64.b64decode(b64, validate=True)
        hash4 = bytes.fromhex(h)
    except ValueError as e:
        raise LoiXacMinh("khóa công khai không đúng dạng note") from e
    if len(hash4) != 4 or len(raw) != 33 or raw[0] != 1 or not ten:
        raise LoiXacMinh("khóa công khai không phải Ed25519 dạng note")
    if hashlib.sha256(ten.encode() + b"\n" + raw).digest()[:4] != hash4:
        raise LoiXacMinh("hash của khóa công khai không khớp")
    return KhoaCongKhai(ten, hash4, Ed25519PublicKey.from_public_bytes(raw[1:]))


@dataclass(frozen=True)
class Checkpoint:
    origin: str
    size: int
    root: bytes


def kiem_checkpoint(van_ban: str, khoa: KhoaCongKhai) -> Checkpoint:
    """Kiểm chữ ký của checkpoint (tlog-checkpoint + signed note) bằng khóa công khai."""
    than, sep, chu_ky = van_ban.partition("\n\n")
    if not sep:
        raise LoiXacMinh("checkpoint thiếu phần chữ ký")
    than += "\n"
    hop_le = False
    for dong in chu_ky.splitlines():
        if not dong.startswith("\u2014 "):
            continue
        parts = dong[2:].split(" ")
        if len(parts) != 2 or parts[0] != khoa.ten:
            continue
        try:
            sig = base64.b64decode(parts[1], validate=True)
        except ValueError:
            continue
        if len(sig) != 68 or sig[:4] != khoa.hash4:
            continue
        try:
            khoa.khoa.verify(sig[4:], than.encode("utf-8"))
            hop_le = True
        except InvalidSignature:
            pass
    if not hop_le:
        raise LoiXacMinh("chữ ký checkpoint không hợp lệ với khóa công khai của sổ cái")
    dong_than = than.split("\n")
    if len(dong_than) < 4:
        raise LoiXacMinh("checkpoint thiếu dòng")
    origin, size, root_b64 = dong_than[0], dong_than[1], dong_than[2]
    if origin != khoa.ten:
        raise LoiXacMinh("origin của checkpoint khác tên khóa")
    try:
        return Checkpoint(origin, int(size), base64.b64decode(root_b64, validate=True))
    except ValueError as e:
        raise LoiXacMinh("checkpoint sai định dạng") from e


# ---------------- Gọi dịch vụ sổ cái ----------------

class SoCai:
    """Client của core/ledger trong mạng nội bộ. Ghi cần token ghi của ứng dụng (OpenBao)."""

    def __init__(self, http: httpx.AsyncClient, token: str, verifier_key: str = "") -> None:
        self._http = http
        self._token = token
        self._vkey = verifier_key.strip()
        self._khoa: KhoaCongKhai | None = doc_khoa_cong_khai(self._vkey) if self._vkey else None

    async def khoa(self) -> KhoaCongKhai:
        # Không cấu hình LEDGER_VERIFIER_KEY: lấy một lần từ ledger nội bộ rồi giữ cố định
        if self._khoa is None:
            r = await self._goi("GET", "/ledger/verifier")
            self._khoa = doc_khoa_cong_khai(r.text)
        return self._khoa

    async def _goi(self, method: str, path: str, **kw: Any) -> httpx.Response:
        try:
            r = await self._http.request(method, path, **kw)
        except httpx.HTTPError as e:
            raise LoiSoCai(f"không gọi được sổ cái: {e.__class__.__name__}") from e
        if r.status_code >= 400:
            try:
                loi = r.json().get("error", "")
            except ValueError:
                loi = ""
            raise LoiSoCai(f"sổ cái trả HTTP {r.status_code} {loi}".strip())
        return r

    async def ghi(self, la: dict[str, Any]) -> dict[str, Any]:
        r = await self._goi("POST", "/ledger/entries", json=la, headers={"Authorization": f"Bearer {self._token}"})
        return r.json()

    async def proof(self, index: int) -> dict[str, Any]:
        return (await self._goi("GET", f"/ledger/proof/{index}")).json()


async def xac_minh(so_cai: SoCai, ban_ghi: dict[str, str | None], ledger_index: int | None,
                   ledger_leaf_hash: bytes | None) -> dict[str, Any]:
    """Băm lại bản ghi trong CSDL và đối chiếu với sổ cái. Trả trạng thái + chi tiết từng bước."""
    sha = sha256_ban_ghi(ban_ghi)
    kq: dict[str, Any] = {"sha256_ban_ghi": sha, "chi_tiet": []}
    if ledger_index is None or ledger_leaf_hash is None:
        kq["trang_thai"] = CHUA_GHI_SO
        kq["chi_tiet"].append("Phiếu chưa được ghi lên sổ cái")
        return kq
    try:
        khoa = await so_cai.khoa()
        p = await so_cai.proof(ledger_index)
    except (LoiSoCai, LoiXacMinh) as e:
        kq["trang_thai"] = KHONG_KIEM_DUOC
        kq["chi_tiet"].append(str(e))
        return kq

    loi: list[str] = []
    try:
        cp = kiem_checkpoint(p["checkpoint"], khoa)
    except LoiXacMinh as e:
        kq["trang_thai"] = KHONG_KHOP
        kq["chi_tiet"].append(str(e))
        return kq
    la = p["leaf"].encode("utf-8")
    lh = leaf_hash(la)
    try:
        noi_dung = json.loads(la)
    except ValueError:
        noi_dung = {}
    if noi_dung.get("type") != LOAI_LA or noi_dung.get("ref") != ban_ghi["id"]:
        loi.append("Lá trên sổ cái không phải của phiếu này")
    if noi_dung.get("sha256") != sha:
        loi.append("SHA-256 của bản ghi hiện tại KHÁC với SHA-256 đã ghi trên sổ cái: bản ghi đã bị sửa sau khi ghi sổ")
    if lh != bytes(ledger_leaf_hash):
        loi.append("Leaf hash lưu trong CSDL khác lá trên sổ cái")
    proof = [bytes.fromhex(h) for h in p.get("proof", [])]
    if cp.size != p.get("tree_size") or not kiem_inclusion(ledger_index, cp.size, lh, proof, cp.root):
        loi.append("Inclusion proof không dẫn tới root của checkpoint đã ký")
    kq.update({
        "trang_thai": KHONG_KHOP if loi else DA_XAC_MINH,
        "checkpoint": {"origin": cp.origin, "tree_size": cp.size, "root_hash": cp.root.hex()},
        "la": p["leaf"],
    })
    kq["chi_tiet"] = loi or ["Bản ghi khớp lá trên sổ cái; lá nằm trong checkpoint đã ký (inclusion proof hợp lệ)"]
    return kq
