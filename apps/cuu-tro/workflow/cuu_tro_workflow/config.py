# SPDX-License-Identifier: Apache-2.0
"""Cấu hình đọc từ biến môi trường (khai báo mẫu trong .env.example của repo)."""

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class Config:
    temporal_address: str
    temporal_namespace: str
    task_queue: str
    # Chuỗi kết nối PostgreSQL bằng role dịch vụ của ứng dụng (cuu_tro_app), chỉ worker dùng.
    # Render từ OpenBao (secret/core/app-db) bởi bao agent, không nằm trong .env.
    db_url: str
    # API kiểm lại chữ ký JWT bằng JWKS của Keycloak (Zero-Trust, giống Hasura)
    jwks_url: str
    jwt_issuer: str
    # Lõi chỉ được gọi qua API Gateway (D-008): API hỏi Hasura qua APISIX /graphql bằng JWT người dùng
    gateway_url: str
    ban_kinh_m: int
    han_xac_nhan_giay: int
    so_lan_tim_doi: int
    cho_tim_lai_giay: int
    # Luồng cảm biến (#30): NATS_URL (user cuu-tro-app) render từ OpenBao secret/app/cuu-tro/nats
    nats_url: str
    # Khai báo stream/consumer JetStream (apps/cuu-tro/nats/streams.json, mount vào container)
    nats_streams_file: str


def load() -> Config:
    realm = os.environ.get("KEYCLOAK_REALM", "disaster")
    kc_internal = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080")
    kc_public = os.environ.get("KEYCLOAK_PUBLIC_URL", "http://localhost:8080")
    return Config(
        temporal_address=os.environ.get("TEMPORAL_ADDRESS", "temporal:7233"),
        temporal_namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        task_queue=os.environ.get("TEMPORAL_TASK_QUEUE", "cuu-tro"),
        db_url=os.environ.get("APP_DB_URL", ""),
        jwks_url=f"{kc_internal}/realms/{realm}/protocol/openid-connect/certs",
        jwt_issuer=f"{kc_public}/realms/{realm}",
        gateway_url=os.environ.get("GATEWAY_INTERNAL_URL", "http://apisix:9080"),
        ban_kinh_m=_int("PHAN_CONG_BAN_KINH_M", 20000),
        han_xac_nhan_giay=_int("PHAN_CONG_HAN_XAC_NHAN_GIAY", 6 * 3600),
        so_lan_tim_doi=_int("PHAN_CONG_SO_LAN_TIM_DOI", 10),
        cho_tim_lai_giay=_int("PHAN_CONG_CHO_TIM_LAI_GIAY", 60),
        nats_url=os.environ.get("NATS_URL", ""),
        nats_streams_file=os.environ.get("NATS_STREAMS_FILE", "/app/nats/streams.json"),
    )
