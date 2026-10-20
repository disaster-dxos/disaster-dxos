# SPDX-License-Identifier: Apache-2.0
"""Kiểm JWT và vai trò ở API: token ký bằng khóa RSA sinh tại chỗ thay cho JWKS của Keycloak."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from cuu_tro_workflow.auth import HASURA_NS, XacThuc, can_vai_tro, vai_tro_tu_claims

ISS = "http://localhost:8080/realms/disaster"
KHOA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KHOA_LA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
xt = XacThuc(ISS, lay_khoa=lambda _t: KHOA.public_key())


def token(vai_tro=("dieu-phoi",), khoa=KHOA, **ghi_de):
    claims = {"sub": "u-1", "iss": ISS, "exp": int(time.time()) + 300, "preferred_username": "dieuphoi01",
              HASURA_NS: {"x-hasura-allowed-roles": list(vai_tro), "x-hasura-default-role": vai_tro[0],
                          "x-hasura-user-id": "u-1"}}
    claims.update(ghi_de)
    return "Bearer " + jwt.encode(claims, khoa, algorithm="RS256")


def ma_loi(fn, *a):
    with pytest.raises(HTTPException) as e:
        fn(*a)
    return e.value.status_code


def test_token_hop_le():
    nd = xt.kiem(token(("cuu-ho",)))
    assert nd.sub == "u-1" and nd.vai_tro == {"cuu-ho"} and nd.co("cuu-ho", "dieu-phoi")


@pytest.mark.parametrize("hdr", [None, "", "Basic abc", "Bearer ", "Bearer khong.phai.jwt"])
def test_thieu_hoac_sai_dinh_dang_thi_401(hdr):
    assert ma_loi(xt.kiem, hdr) == 401


def test_sai_chu_ky_het_han_sai_issuer_thi_401():
    assert ma_loi(xt.kiem, token(khoa=KHOA_LA)) == 401
    assert ma_loi(xt.kiem, token(exp=int(time.time()) - 10)) == 401
    assert ma_loi(xt.kiem, token(iss="http://ke-gia/realms/disaster")) == 401


def test_khong_chap_nhan_alg_none():
    t = jwt.encode({"sub": "u", "iss": ISS, "exp": int(time.time()) + 60}, None, algorithm="none")
    assert ma_loi(xt.kiem, "Bearer " + t) == 401


def test_vai_tro():
    assert vai_tro_tu_claims({}) == frozenset()
    assert vai_tro_tu_claims({HASURA_NS: {"x-hasura-allowed-roles": "cuu-ho"}}) == {"cuu-ho"}
    nd = xt.kiem(token(("tinh-nguyen",)))
    assert ma_loi(can_vai_tro, nd, "dieu-phoi") == 403
    can_vai_tro(xt.kiem(token(("dieu-phoi",))), "dieu-phoi")


def test_api_chan_truoc_khi_goi_temporal():
    # Không chạy lifespan (không Temporal, không gateway): chỉ kiểm các nhánh từ chối sớm
    from fastapi.testclient import TestClient

    from cuu_tro_workflow.api import app

    app.state.xac_thuc = xt
    c = TestClient(app)
    inc = "b0000000-0000-4000-8000-000000000004"
    assert c.post(f"/phan-cong/{inc}").status_code == 401
    assert c.post(f"/phan-cong/{inc}", headers={"Authorization": token(("tinh-nguyen",))}).status_code == 403
    assert c.post(f"/phan-cong/{inc}", headers={"Authorization": token(("cuu-ho",))}).status_code == 403
    assert c.post("/phan-cong/khong-phai-uuid", headers={"Authorization": token()}).status_code == 422
    assert c.get("/hello-123", headers={"Authorization": token()}).status_code == 404
    assert c.post(f"/phan-cong-{inc}/xac-nhan", headers={"Authorization": token(("tinh-nguyen",))}).status_code == 403
