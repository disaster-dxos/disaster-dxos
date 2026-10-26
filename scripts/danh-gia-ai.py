#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Đánh giá AI bóc tách tin kêu cứu (#102) trên bộ tin mẫu giả, gọi THẬT qua gateway với nhà cung cấp
đang cấu hình của cuu-tro-api (LLM_PROVIDER). Dùng để so Qwen2.5 7B (ollama) với bộ luật (gia-lap).

In bảng từng tin: trường đúng/sai so với "mong_doi", thời gian, có dùng bộ luật dự phòng không; cuối cùng là tỷ
lệ đúng theo trường và thời gian trung vị. Chỉ dùng thư viện chuẩn. Không ghi gì vào CSDL (endpoint không tạo tin).

Dùng: set -a; . ./.env; set +a; python3 scripts/danh-gia-ai.py [tệp-tin-mẫu.json]
"""

import json
import os
import statistics
import sys
import urllib.parse
import urllib.request
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
MAU = GOC / "apps/cuu-tro/workflow/cuu_tro_workflow/du_lieu/tin_keu_cuu_mau.json"
GW = f"http://localhost:{os.environ.get('APISIX_PORT', '9080')}"
KC = os.environ.get("KEYCLOAK_PUBLIC_URL", "http://localhost:8080")
REALM = os.environ.get("KEYCLOAK_REALM", "disaster")


def token() -> str:
    body = urllib.parse.urlencode({"grant_type": "password", "client_id": "dxos-dev-cli", "scope": "openid",
                                   "username": "dieuphoi01", "password": os.environ["KC_DEMO_USER_PASSWORD"]})
    with urllib.request.urlopen(f"{KC}/realms/{REALM}/protocol/openid-connect/token", body.encode(), timeout=30) as r:
        return json.load(r)["access_token"]


def boc_tach(tok: str, van_ban: str, nguon: str) -> dict:
    req = urllib.request.Request(f"{GW}/workflow/ai/boc-tach", method="POST",
                                 data=json.dumps({"van_ban": van_ban, "nguon": nguon}).encode(),
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def dung(k: str, v, d: dict) -> bool:
    if k == "nhu_cau_co":
        return set(v) <= set(d["nhu_cau"])
    if k == "dia_chi_co":
        return bool(d["address_text"]) and v.lower() in d["address_text"].lower()
    return d.get(k) == v


def main() -> int:
    mau = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else MAU).read_text())
    tok = token()
    dem: dict[str, list[bool]] = {}
    thoi_gian = []
    nha_cung_cap = "?"
    for i, m in enumerate(mau):
        kq = boc_tach(tok, m["van_ban"], m.get("nguon", "van_ban"))
        d, ai = kq["de_xuat"], kq["ai"]
        nha_cung_cap = f"{ai['nha_cung_cap']} {ai['mo_hinh'] or ''}".strip()
        thoi_gian.append(ai["thoi_gian_ms"])
        sai = []
        for k, v in m["mong_doi"].items():
            ok = dung(k, v, d)
            dem.setdefault(k, []).append(ok)
            if not ok:
                sai.append(f"{k}: mong đợi {v!r}, nhận {d.get(k) if k not in ('nhu_cau_co', 'dia_chi_co') else (d['nhu_cau'], d['address_text'])!r}")
        print(f"tin {i}: {ai['thoi_gian_ms']:>6} ms{' (dự phòng)' if ai['du_phong'] else ''}  "
              f"{'đúng hết' if not sai else '; '.join(sai)}")
    print(f"\nNhà cung cấp: {nha_cung_cap}; {len(mau)} tin; thời gian trung vị {statistics.median(thoi_gian):.0f} ms, "
          f"lớn nhất {max(thoi_gian)} ms")
    tong = [x for v in dem.values() for x in v]
    for k, v in dem.items():
        print(f"  {k:<16} {sum(v)}/{len(v)}")
    print(f"  {'TỔNG':<16} {sum(tong)}/{len(tong)} ({100 * sum(tong) / len(tong):.0f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
