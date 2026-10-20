# SPDX-License-Identifier: Apache-2.0
"""Đọc người dùng và vai trò từ JWT Keycloak mà APISIX chuyển tiếp (header Authorization).

APISIX đã kiểm token (openid-connect, JWKS) trước khi request tới đây. API vẫn kiểm lại chữ ký,
hạn và issuer bằng JWKS của Keycloak (Zero-Trust, giống Hasura): cổng nội bộ của API không tin
header nào chỉ vì request đến từ mạng Docker.
Vai trò lấy từ claim Hasura (#13): https://hasura.io/jwt/claims → x-hasura-allowed-roles.
"""

from dataclasses import dataclass
from typing import Any, Callable

import jwt
from fastapi import HTTPException

HASURA_NS = "https://hasura.io/jwt/claims"

VAI_TRO_DIEU_PHOI = "dieu-phoi"
VAI_TRO_CUU_HO = "cuu-ho"
VAI_TRO_TINH_NGUYEN = "tinh-nguyen"


@dataclass(frozen=True)
class NguoiDung:
    sub: str
    ten_dang_nhap: str
    vai_tro: frozenset[str]
    # Token gốc: chuyển tiếp khi API hỏi Hasura thay mặt người dùng (qua gateway)
    token: str

    def co(self, *vai_tro: str) -> bool:
        return any(v in self.vai_tro for v in vai_tro)


def vai_tro_tu_claims(claims: dict[str, Any]) -> frozenset[str]:
    ns = claims.get(HASURA_NS) or {}
    roles = ns.get("x-hasura-allowed-roles") or []
    if isinstance(roles, str):
        roles = [roles]
    return frozenset(r for r in roles if isinstance(r, str))


class XacThuc:
    """Kiểm JWT. `lay_khoa(token)` trả khóa công khai; mặc định lấy theo `kid` từ JWKS (có cache)."""

    def __init__(self, issuer: str, jwks_url: str | None = None, lay_khoa: Callable[[str], Any] | None = None):
        self._issuer = issuer
        if lay_khoa is None:
            if not jwks_url:
                raise ValueError("cần jwks_url hoặc lay_khoa")
            jwks = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=300, timeout=5)
            lay_khoa = lambda t: jwks.get_signing_key_from_jwt(t).key  # noqa: E731
        self._lay_khoa = lay_khoa

    def kiem(self, authorization: str | None) -> NguoiDung:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Thiếu Bearer token", headers={"WWW-Authenticate": "Bearer"})
        token = authorization[7:].strip()
        try:
            claims = jwt.decode(
                token,
                self._lay_khoa(token),
                algorithms=["RS256"],
                issuer=self._issuer,
                # Access token Keycloak có aud "account"/không có aud tùy client: không kiểm aud,
                # giống cấu hình HASURA_GRAPHQL_JWT_SECRET
                options={"verify_aud": False, "require": ["exp", "iss", "sub"]},
            )
        except (jwt.PyJWTError, jwt.PyJWKClientError) as e:
            raise HTTPException(401, f"Token không hợp lệ: {e}", headers={"WWW-Authenticate": "Bearer"}) from e
        return NguoiDung(
            sub=claims["sub"],
            ten_dang_nhap=claims.get("preferred_username", ""),
            vai_tro=vai_tro_tu_claims(claims),
            token=token,
        )


def can_vai_tro(nd: NguoiDung, *vai_tro: str) -> None:
    """403 nếu người dùng không có vai trò nào trong danh sách."""
    if not nd.co(*vai_tro):
        raise HTTPException(403, f"Cần vai trò: {', '.join(vai_tro)}")
