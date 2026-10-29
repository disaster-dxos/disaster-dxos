#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Đăng nhập Grafana bằng SSO Keycloak như trình duyệt (#126), dùng trong scripts/smoke-grafana.sh.

Đi đúng đường của trình duyệt, chỉ thư viện chuẩn, tự theo dõi từng chuyển hướng:
  GET  <grafana>/login/generic_oauth  → 302 sang Keycloak (client dxos-grafana, PKCE S256)
  GET  trang đăng nhập Keycloak, POST tên + mật khẩu
  (vai dieu-phoi) trang cài OTP: đọc totpSecret, tính mã TOTP (RFC 6238, SHA-1, 6 số, 30 giây, chính sách OTP mặc định của realm), gửi
  GET  <grafana>/login/generic_oauth?code=…&state=… (qua APISIX) → cookie grafana_session
  GET  /api/user, /api/user/orgs, /api/dashboards/uid/<uid>, quyền dashboards:create; rồi /logout
In một dòng JSON kết quả. Mật khẩu đọc từ biến môi trường SSO_PASSWORD, không lên dòng lệnh.
Dùng: SSO_PASSWORD=… grafana-sso.py <grafana URL> <tên đăng nhập> [uid dashboard]
"""

from __future__ import annotations

import hashlib
import hmac
import html
import http.cookiejar
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 30


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, PLR0913
        return None


class _LocalhostSecure(http.cookiejar.DefaultCookiePolicy):
    """Như trình duyệt: http://localhost là ngữ cảnh an toàn, gửi cả cookie Secure (Keycloak đặt Secure cho
    AUTH_SESSION_ID dù chạy HTTP)."""

    def return_ok_secure(self, cookie, request):  # noqa: ANN001
        host = urllib.parse.urlsplit(request.get_full_url()).hostname
        return host in ("localhost", "127.0.0.1") or super().return_ok_secure(cookie, request)


JAR = http.cookiejar.CookieJar(_LocalhostSecure())
OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(JAR), _NoRedirect)


def goi(url: str, data: dict | None = None, headers: dict | None = None, method: str | None = None):
    """Một request, không theo chuyển hướng. Trả (mã HTTP, Location, body)."""
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        r = OPENER.open(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as e:
        r = e
    loc = r.headers.get("Location") or ""
    return r.status, urllib.parse.urljoin(url, loc) if loc else "", r.read().decode("utf-8", "replace")


def form_action(page: str) -> str:
    m = re.search(r'<form[^>]*action="([^"]+)"', page)
    if not m:
        raise SystemExit(json.dumps({"loi": "không thấy form trên trang Keycloak"}))
    return html.unescape(m.group(1))


def totp(secret: str, t: float | None = None) -> str:
    # Trường ẩn totpSecret của Keycloak là khóa gốc (chuỗi ASCII), bản base32 chỉ để hiện cho người nhập tay
    key = secret.encode()
    mac = hmac.new(key, struct.pack(">Q", int((t or time.time()) // 30)), hashlib.sha1).digest()
    o = mac[-1] & 0x0F
    return f"{(struct.unpack('>I', mac[o : o + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


def main() -> None:
    g, user = sys.argv[1].rstrip("/"), sys.argv[2]
    uid = sys.argv[3] if len(sys.argv) > 3 else ""
    kq: dict = {"user": user}

    code, loc, _ = goi(g + "/login/generic_oauth")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(loc).query))
    kq["chuyen_keycloak"] = code == 302 and "/protocol/openid-connect/auth" in loc
    kq["client_id"] = q.get("client_id", "")
    kq["pkce"] = q.get("code_challenge_method", "") if q.get("code_challenge") else ""
    kq["redirect_uri"] = q.get("redirect_uri", "")
    if not kq["chuyen_keycloak"]:
        print(json.dumps(kq, ensure_ascii=False))
        return

    _, _, page = goi(loc)
    code, loc, page = goi(form_action(page), {"username": user, "password": os.environ["SSO_PASSWORD"]})
    kq["otp"] = False
    if code == 302 and "execution=CONFIGURE_TOTP" in loc:
        # Vai dieu-phoi bị bắt cài OTP (luồng browser-otp-dieu-phoi của realm), cả khi vào Grafana
        kq["otp"] = True
        _, _, page = goi(loc)
        m = re.search(r'name="totpSecret"[^>]*value="([^"]+)"|value="([^"]+)"[^>]*name="totpSecret"', page)
        if not m:
            raise SystemExit(json.dumps({"loi": "không thấy totpSecret trên trang cài OTP"}))
        secret = html.unescape(m.group(1) or m.group(2))
        code, loc, page = goi(
            form_action(page), {"totp": totp(secret), "totpSecret": secret, "userLabel": "smoke-grafana", "mode": "manual"}
        )
    kq["ve_grafana"] = code == 302 and loc.startswith(g + "/login/generic_oauth")
    if not kq["ve_grafana"]:
        kq["keycloak_tra"] = f"{code} {loc[:120]}"
        print(json.dumps(kq, ensure_ascii=False))
        return

    code, loc, _ = goi(loc)  # callback qua APISIX: Grafana đổi code (kèm PKCE verifier) lấy token
    kq["callback"] = f"{code} {urllib.parse.urlsplit(loc).path}"
    kq["co_phien"] = any(c.name == "grafana_session" for c in JAR)
    if not kq["co_phien"]:
        print(json.dumps(kq, ensure_ascii=False))
        return

    code, _, body = goi(g + "/api/user")
    u = json.loads(body) if code == 200 else {}
    kq["login"], kq["email"], kq["grafana_admin"] = u.get("login", ""), u.get("email", ""), u.get("isGrafanaAdmin")
    kq["auth_module"] = ",".join(u.get("authLabels") or [])
    code, _, body = goi(g + "/api/user/orgs")
    kq["role"] = json.loads(body)[0]["role"] if code == 200 else f"HTTP {code}"
    if uid:
        code, _, body = goi(g + "/api/dashboards/uid/" + uid)
        kq["dashboard"] = json.loads(body)["dashboard"]["title"] if code == 200 else f"HTTP {code}"
        kq["so_panel"] = len(json.loads(body)["dashboard"]["panels"]) if code == 200 else 0
    # Quyền ghi theo RBAC của Grafana (Editor tạo được dashboard, Viewer không). Chỉ đọc, không tạo gì: gateway
    # không cho DELETE nên dashboard tạo thử sẽ không dọn được.
    code, _, body = goi(g + "/api/access-control/user/actions")
    kq["tao_dashboard"] = "dashboards:create" in json.loads(body) if code == 200 else f"HTTP {code}"
    code, loc, _ = goi(g + "/logout")
    kq["dang_xuat"] = f"{code} {loc.split('?')[0]}"
    print(json.dumps(kq, ensure_ascii=False))


if __name__ == "__main__":
    main()
