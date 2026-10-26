# SPDX-License-Identifier: Apache-2.0
"""Hàng chờ duyệt tin kêu cứu do AI bóc tách (#104, Human-in-the-loop, nối tiếp #102).

Luồng:
  1. POST /ai/boc-tach {"van_ban", "nguon", "vao_hang_cho": true} (dieu-phoi, tinh-nguyen): API bóc tách rồi
     lưu văn bản gốc + toàn bộ đề xuất của AI vào bảng ai_intake_reviews (migration 0014), trạng thái cho_duyet.
     Đề xuất do API tạo và lưu: client không tự khai được "AI đã đề xuất gì".
  2. Điều phối viên đọc hàng chờ qua /graphql (Hasura, chỉ dieu-phoi thấy văn bản và đề xuất).
  3. POST /hang-cho/{id}/duyet (dieu-phoi), body tùy chọn {"tin_keu_cuu": {…}} là body ĐẦY ĐỦ của POST
     /keu-cuu sau khi người duyệt sửa (thiếu thì dùng nguyên đề xuất). Kiểm bằng đúng Poka-yoke của /keu-cuu
     (keu_cuu.kiem_tra), rồi trong MỘT transaction: khóa dòng hàng chờ (FOR UPDATE), tạo tin bằng câu INSERT
     của /keu-cuu (trigger chặn trùng + outbox phân công vẫn chạy), đánh dấu da_duyet kèm nội dung cuối, trường
     đã sửa, người duyệt, thời điểm. Hai người cùng duyệt: người sau nhận 409.
  4. POST /hang-cho/{id}/huy (dieu-phoi) {"ly_do"}: da_huy, không tạo tin.

Logic thuần trừ lớp SoHangCho (asyncpg). Không ghi văn bản tin hay SĐT ra log.
"""

import json
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any

import asyncpg

from . import keu_cuu

TRANG_THAI = ("cho_duyet", "da_duyet", "da_huy")
LY_DO_TOI_DA = 500
# Body duyệt = một tin kêu cứu (≤ 16 KiB như /keu-cuu) bọc trong {"tin_keu_cuu": …}
BODY_TOI_DA = keu_cuu.BODY_TOI_DA + 1024

# Đọc đề xuất của AI qua Hasura bằng JWT của người duyệt: role dịch vụ cuu_tro_app không đọc được cột có dữ
# liệu người dân (ai_result chứa SĐT, tên), như reporter_phone của incidents.
Q_MUC = """query($id: uuid!) { ai_intake_reviews_by_pk(id: $id) {
  id status ai_result reviewed_at reviewed_by_name incident_id } }"""


class KhongCo(Exception):
    """Không có mục này trong hàng chờ."""


class DaXuLy(Exception):
    """Mục đã duyệt hoặc đã hủy (có thể bởi người khác ngay trước đó)."""

    def __init__(self, dong: dict[str, Any]) -> None:
        super().__init__(dong.get("status"))
        self.dong = dong


# ---------------- Logic thuần ----------------
def body_cuoi(tin: keu_cuu.TinKeuCuu) -> dict[str, Any]:
    """Tin đã qua Poka-yoke → body đã chuẩn hóa (SĐT dạng 0…, mô tả bỏ khoảng trắng) để lưu vết."""
    return asdict(tin)


def truong_da_sua(ai_body: dict[str, Any], cuoi: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Các trường của /keu-cuu mà người duyệt đổi so với đề xuất: {trường: {"ai": …, "nguoi": …}}.

    So trên giá trị đã chuẩn hóa: gõ lại SĐT có dấu cách hay "+84" không tính là sửa. Đề xuất không có trường
    (AI không tìm thấy) là None; người duyệt bổ sung (vd chọn tọa độ trên bản đồ) thì tính là sửa.
    """
    sua: dict[str, dict[str, Any]] = {}
    for k in keu_cuu.TRUONG:
        a = ai_body.get(k)
        if k == "reporter_phone" and isinstance(a, str):
            a = keu_cuu.chuan_hoa_sdt(a) or a
        b = cuoi.get(k)
        if a != b:
            sua[k] = {"ai": a, "nguoi": b}
    return sua


def kiem_duyet(d: Any, ai_body: dict[str, Any]) -> dict[str, Any] | list[keu_cuu.LoiTruong]:
    """Body duyệt {} hoặc {"tin_keu_cuu": {…}} → body /keu-cuu cần kiểm (chưa qua Poka-yoke) hoặc lỗi.

    tin_keu_cuu là body đầy đủ (không phải phần thay đổi). Thiếu `source` thì giữ nguồn của đề xuất (Zalo, SMS…)
    để thống kê theo kênh không bị lẫn với tin gửi từ app.
    """
    if not isinstance(d, dict):
        return [keu_cuu.LoiTruong("body", "Nội dung gửi lên phải là một đối tượng JSON.")]
    loi = [keu_cuu.LoiTruong(str(k)[:50], "Trường không được hỗ trợ (kiểm tra lại tên trường).")
           for k in d if k != "tin_keu_cuu"]
    tin = d.get("tin_keu_cuu", ai_body)
    if not isinstance(tin, dict):
        loi.append(keu_cuu.LoiTruong("tin_keu_cuu", "tin_keu_cuu phải là một đối tượng JSON (body của /keu-cuu)."))
    if loi:
        return loi
    body = dict(tin)
    if "source" not in body and ai_body.get("source") in keu_cuu.NGUON:
        body["source"] = ai_body["source"]
    return body


def kiem_huy(d: Any) -> str | None | list[keu_cuu.LoiTruong]:
    """Body hủy {} hoặc {"ly_do": "…"} → lý do (None nếu trống) hoặc lỗi theo trường."""
    if not isinstance(d, dict):
        return [keu_cuu.LoiTruong("body", "Nội dung gửi lên phải là một đối tượng JSON.")]
    loi = [keu_cuu.LoiTruong(str(k)[:50], "Trường không được hỗ trợ (kiểm tra lại tên trường).")
           for k in d if k != "ly_do"]
    ly_do = keu_cuu._chuoi(d, "ly_do", LY_DO_TOI_DA, loi, "lý do hủy")
    return loi if loi else ly_do


def loi_da_xu_ly(dong: dict[str, Any]) -> dict[str, Any]:
    tt = dong.get("status")
    ai = dong.get("reviewed_by_name") or "người khác"
    luc = dong.get("reviewed_at")
    luc_s = luc.isoformat() if isinstance(luc, datetime) else luc
    viec = "duyệt" if tt == "da_duyet" else "hủy"
    return {"ma": "da_xu_ly",
            "thong_bao": f"Tin này đã được {viec} bởi {ai}; không xử lý lại được.",
            "trang_thai": tt, "reviewed_by_name": dong.get("reviewed_by_name"), "reviewed_at": luc_s,
            "incident_id": str(dong["incident_id"]) if dong.get("incident_id") else None}


# ---------------- Lưu trữ (role dịch vụ cuu_tro_app, migration 0014) ----------------
class SoHangCho:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def them(self, *, van_ban: str, nguon: str, ket_qua: dict[str, Any], nguoi_gui: str,
                   ten_nguoi_gui: str | None, vai_tro: str) -> dict[str, Any]:
        ai = ket_qua["ai"]
        row = await self._pool.fetchrow(
            """INSERT INTO cuu_tro.ai_intake_reviews
                 (raw_text, text_source, ai_result, ai_provider, ai_model, ai_fallback, ai_duration_ms, ai_urgency,
                  ai_valid, submitted_by, submitted_by_name, submitted_role)
               VALUES ($1, $2, $3::jsonb, $4, $5, $6, $7, $8, $9, $10, $11, $12)
               RETURNING id, status, created_at""",
            van_ban, nguon, json.dumps(ket_qua, ensure_ascii=False), ai["nha_cung_cap"], ai["mo_hinh"],
            ai["du_phong"], ai["thoi_gian_ms"], ket_qua["de_xuat"]["urgency"], ket_qua["poka_yoke"]["hop_le"],
            nguoi_gui, (ten_nguoi_gui or None) and ten_nguoi_gui[:100], vai_tro,
        )
        return {"id": str(row["id"]), "trang_thai": row["status"], "tao_luc": row["created_at"].isoformat()}

    async def _khoa(self, conn: asyncpg.Connection, ma: str) -> dict[str, Any]:
        row = await conn.fetchrow(
            """SELECT status, submitted_by, reviewed_at, reviewed_by_name, incident_id
                 FROM cuu_tro.ai_intake_reviews WHERE id = $1 FOR UPDATE""", uuid.UUID(ma))
        if row is None:
            raise KhongCo(ma)
        if row["status"] != "cho_duyet":
            raise DaXuLy(dict(row))
        return dict(row)

    async def duyet(self, ma: str, tin: keu_cuu.TinKeuCuu, *, sua: dict[str, Any], nguoi_duyet: str,
                    ten_nguoi_duyet: str | None) -> dict[str, Any]:
        """Tạo tin + đánh dấu đã duyệt trong một transaction. Lỗi trùng của trigger (UniqueViolationError
        incidents_no_duplicate) đi ra ngoài; transaction rollback nên mục vẫn cho_duyet."""
        async with self._pool.acquire() as conn, conn.transaction():
            muc = await self._khoa(conn, ma)
            # Tin thuộc người đưa vào hàng chờ (tình nguyện viên chuyển tin thấy được tin của mình qua Hasura);
            # người chịu trách nhiệm duyệt nằm ở vết duyệt
            tin_moi = await conn.fetchrow(keu_cuu.SQL_THEM_TIN, *keu_cuu.tham_so_them_tin(tin, muc["submitted_by"]))
            luc = await conn.fetchval(
                """UPDATE cuu_tro.ai_intake_reviews
                      SET status = 'da_duyet', final_body = $2::jsonb, edited_fields = $3::jsonb, reviewed_by = $4,
                          reviewed_by_name = $5, reviewed_at = now(), incident_id = $6
                    WHERE id = $1
                RETURNING reviewed_at""",
                uuid.UUID(ma), json.dumps(body_cuoi(tin), ensure_ascii=False), json.dumps(sua, ensure_ascii=False),
                nguoi_duyet, (ten_nguoi_duyet or None) and ten_nguoi_duyet[:100], tin_moi["id"],
            )
        return {"tin": dict(tin_moi), "reviewed_at": luc}

    async def huy(self, ma: str, ly_do: str | None, *, nguoi_duyet: str, ten_nguoi_duyet: str | None) -> datetime:
        async with self._pool.acquire() as conn, conn.transaction():
            await self._khoa(conn, ma)
            return await conn.fetchval(
                """UPDATE cuu_tro.ai_intake_reviews
                      SET status = 'da_huy', cancel_reason = $2, reviewed_by = $3, reviewed_by_name = $4,
                          reviewed_at = now()
                    WHERE id = $1
                RETURNING reviewed_at""",
                uuid.UUID(ma), ly_do, nguoi_duyet, (ten_nguoi_duyet or None) and ten_nguoi_duyet[:100],
            )
