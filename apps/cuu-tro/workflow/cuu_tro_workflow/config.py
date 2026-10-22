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
    # Chuỗi kết nối PostgreSQL bằng role dịch vụ của ứng dụng (cuu_tro_app): worker, consumer cảm biến,
    # API (chỉ để ghi incident_media, #27).
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
    # Ảnh hiện trường (#27). Khóa S3 của ứng dụng (secret/app/cuu-tro/s3) do bao agent render, chỉ
    # cuu-tro-api có. API ghi S3 thẳng trong mạng nội bộ; link xem ký cho URL công khai của gateway.
    s3_endpoint: str = "http://seaweedfs:8333"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"
    anh_bucket: str = "cuu-tro-media"
    anh_max_bytes: int = 10 * 1024 * 1024
    # Hạn link xem mặc định = tối đa (giây); client xin ngắn hơn bằng ?han_giay=
    anh_link_han_giay: int = 300
    gateway_public_url: str = "http://localhost:9080"
    # Sổ cái minh bạch (#28): core/ledger trong mạng nội bộ (ghi không đi qua gateway: APISIX chặn mọi
    # phương thức ghi /ledger/*). Token ghi của ứng dụng (secret/app/cuu-tro/ledger) do bao agent render.
    # Khóa công khai (verifier) để tự kiểm chữ ký checkpoint; trống = lấy một lần từ ledger nội bộ.
    ledger_url: str = "http://ledger:8090"
    ledger_write_token: str = ""
    ledger_verifier_key: str = ""


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
        s3_endpoint=os.environ.get("S3_ENDPOINT", "http://seaweedfs:8333"),
        s3_access_key=os.environ.get("S3_ACCESS_KEY", ""),
        s3_secret_key=os.environ.get("S3_SECRET_KEY", ""),
        s3_region=os.environ.get("S3_REGION", "us-east-1"),
        anh_bucket=os.environ.get("ANH_BUCKET", "cuu-tro-media"),
        anh_max_bytes=_int("ANH_MAX_BYTES", 10 * 1024 * 1024),
        anh_link_han_giay=_int("ANH_LINK_HAN_GIAY", 300),
        gateway_public_url=os.environ.get("GATEWAY_PUBLIC_URL", "http://localhost:9080"),
        ledger_url=os.environ.get("LEDGER_URL", "http://ledger:8090"),
        ledger_write_token=os.environ.get("LEDGER_WRITE_TOKEN", ""),
        ledger_verifier_key=os.environ.get("LEDGER_VERIFIER_KEY", ""),
    )
