# SPDX-License-Identifier: Apache-2.0
"""Ký request S3 (AWS Signature V4) và client S3 tối thiểu cho ảnh hiện trường (#27).

Chỉ cần 3 thao tác trên SeaweedFS: ghi object (PUT), xóa object (DELETE) khi ghi CSDL lỗi, và ký URL
xem (GET presigned) cho client. Tự ký bằng hashlib/hmac thay cho boto3 (~100 MB khi cài): ít phụ thuộc,
image nhỏ; đúng thuật toán được kiểm bằng ví dụ chính thức của AWS (tests/test_cuu_tro_anh.py).
Tham chiếu: https://docs.aws.amazon.com/AmazonS3/latest/API/sig-v4-authenticating-requests.html
"""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

import httpx

ALGO = "AWS4-HMAC-SHA256"
# SHA-256 của body rỗng (GET/DELETE)
SHA256_RONG = hashlib.sha256(b"").hexdigest()


def _ma_hoa(s: str, giu_gach: bool = False) -> str:
    # URI-encode theo SigV4: giữ A-Z a-z 0-9 - _ . ~ (và "/" trong path)
    return quote(s, safe="-_.~/" if giu_gach else "-_.~")


def _khoa_ky(secret_key: str, ngay: str, region: str) -> bytes:
    k = ("AWS4" + secret_key).encode()
    for phan in (ngay, region, "s3", "aws4_request"):
        k = hmac.new(k, phan.encode(), hashlib.sha256).digest()
    return k


def _chu_ky(secret_key: str, ngay: str, region: str, amz_date: str, pham_vi: str, creq: str) -> str:
    sts = "\n".join([ALGO, amz_date, pham_vi, hashlib.sha256(creq.encode()).hexdigest()])
    return hmac.new(_khoa_ky(secret_key, ngay, region), sts.encode(), hashlib.sha256).hexdigest()


def _thoi_diem(luc: datetime | None) -> tuple[str, str]:
    luc = (luc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return luc.strftime("%Y%m%dT%H%M%SZ"), luc.strftime("%Y%m%d")


def presign(
    *, method: str, host: str, path: str, access_key: str, secret_key: str, han_giay: int,
    region: str = "us-east-1", luc: datetime | None = None,
) -> str:
    """Trả chuỗi query X-Amz-* (đã có chữ ký) cho URL presigned. `path` là path S3 /<bucket>/<key>."""
    amz_date, ngay = _thoi_diem(luc)
    pham_vi = f"{ngay}/{region}/s3/aws4_request"
    q = {
        "X-Amz-Algorithm": ALGO,
        "X-Amz-Credential": f"{access_key}/{pham_vi}",
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(han_giay),
        "X-Amz-SignedHeaders": "host",
    }
    cq = "&".join(f"{_ma_hoa(k)}={_ma_hoa(v)}" for k, v in sorted(q.items()))
    creq = "\n".join([method, _ma_hoa(path, True), cq, f"host:{host}\n", "host", "UNSIGNED-PAYLOAD"])
    return cq + "&X-Amz-Signature=" + _chu_ky(secret_key, ngay, region, amz_date, pham_vi, creq)


def ky_header(
    *, method: str, host: str, path: str, payload_sha256: str, access_key: str, secret_key: str,
    region: str = "us-east-1", luc: datetime | None = None, header_khac: dict[str, str] | None = None,
) -> dict[str, str]:
    """Header ký SigV4 cho request không có query string (Authorization, x-amz-date, x-amz-content-sha256).

    Ký kèm SHA-256 thật của body: S3 tính lại và từ chối nếu nội dung bị đổi trên đường đi.
    `header_khac` (vd range) được ký cùng và phải gửi kèm request.
    """
    amz_date, ngay = _thoi_diem(luc)
    pham_vi = f"{ngay}/{region}/s3/aws4_request"
    h = {"host": host, "x-amz-content-sha256": payload_sha256, "x-amz-date": amz_date}
    h.update({k.lower(): v.strip() for k, v in (header_khac or {}).items()})
    ten = sorted(h)
    signed = ";".join(ten)
    creq = "\n".join([method, _ma_hoa(path, True), "", "".join(f"{k}:{h[k]}\n" for k in ten), signed, payload_sha256])
    sig = _chu_ky(secret_key, ngay, region, amz_date, pham_vi, creq)
    out = {k: v for k, v in h.items() if k != "host"}
    out["Authorization"] = f"{ALGO} Credential={access_key}/{pham_vi}, SignedHeaders={signed}, Signature={sig}"
    return out


class LoiS3(Exception):
    pass


@dataclass
class KhoAnh:
    """Bucket ảnh trên SeaweedFS, ký bằng khóa S3 của ứng dụng (định danh cuu-tro-app, chỉ bucket cuu-tro-*).

    Ghi/xóa: gọi thẳng S3 trong mạng nội bộ (`endpoint`, vd http://seaweedfs:8333).
    Link xem: ký cho host công khai của gateway; client mở <gateway>/files/<bucket>/<key>?X-Amz-...
    (APISIX bỏ tiền tố /files, SeaweedFS tính chữ ký theo X-Forwarded-Host = host của gateway).
    """

    endpoint: str
    bucket: str
    access_key: str
    secret_key: str
    gateway_public_url: str
    http: httpx.AsyncClient
    region: str = "us-east-1"

    def _path(self, key: str) -> str:
        return f"/{self.bucket}/{key}"

    async def _goi(self, method: str, key: str, body: bytes = b"", content_type: str | None = None) -> int:
        host = urlsplit(self.endpoint).netloc
        sha = hashlib.sha256(body).hexdigest() if body else SHA256_RONG
        h = ky_header(method=method, host=host, path=self._path(key), payload_sha256=sha,
                      access_key=self.access_key, secret_key=self.secret_key, region=self.region)
        if content_type:
            h["Content-Type"] = content_type
        r = await self.http.request(method, self.endpoint + _ma_hoa(self._path(key), True), content=body, headers=h)
        return r.status_code

    async def ghi(self, key: str, du_lieu: bytes, content_type: str) -> None:
        ma = await self._goi("PUT", key, du_lieu, content_type)
        if ma != 200:
            raise LoiS3(f"S3 PUT {key} trả HTTP {ma}")

    async def doc(self, key: str) -> bytes | None:
        """GET một object; None nếu không có (404)."""
        host = urlsplit(self.endpoint).netloc
        h = ky_header(method="GET", host=host, path=self._path(key), payload_sha256=SHA256_RONG,
                      access_key=self.access_key, secret_key=self.secret_key, region=self.region)
        r = await self.http.get(self.endpoint + _ma_hoa(self._path(key), True), headers=h)
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            raise LoiS3(f"S3 GET {key} trả HTTP {r.status_code}")
        return r.content

    async def xoa(self, key: str) -> None:
        ma = await self._goi("DELETE", key)
        if ma not in (200, 204):
            raise LoiS3(f"S3 DELETE {key} trả HTTP {ma}")

    def link_xem(self, key: str, han_giay: int, luc: datetime | None = None) -> str:
        goc = self.gateway_public_url.rstrip("/")
        q = presign(method="GET", host=urlsplit(goc).netloc, path=self._path(key), access_key=self.access_key,
                    secret_key=self.secret_key, han_giay=han_giay, region=self.region, luc=luc)
        return f"{goc}/files{_ma_hoa(self._path(key), True)}?{q}"
