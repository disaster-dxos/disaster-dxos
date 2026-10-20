#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Kiểm thử sổ cái minh bạch (#28, D-007), gọi THẬT qua APISIX bằng token Keycloak của user mẫu:
# (1) lõi: checkpoint/tile/verifier đọc công khai qua /ledger/*, khóa công khai khớp OpenBao; mọi phương
#     thức ghi /ledger/* từ ngoài gateway → 403; ledger không mở cổng ra máy host; trong mạng nội bộ không
#     có/sai token ghi → 401; .state/ không đọc được; log ledger không chứa khóa ký;
# (2) dieu-phoi lập 3 phiếu nhập/xuất qua /workflow/kho/phieu → mỗi phiếu có ledger_index trong CSDL;
#     cuu-ho/không token bị chặn; GraphQL không còn đường lập phiếu (không lọt sổ cái);
# (3) trang công khai /workflow/minh-bach/phieu/{ma} (không đăng nhập) → "da_xac_minh"; CLI
#     ledger-verify chạy độc lập (chỉ dùng checkpoint + tile công khai qua gateway) → ĐÃ XÁC MINH;
# (4) sửa tay số lượng một phiếu trong CSDL (tắt trigger bất biến bằng superuser) → trang công khai và CLI
#     báo "không khớp"; khôi phục → lại "da_xac_minh";
# (5) gửi lại đúng lá cũ → chống trùng trả index cũ; ghi lại sổ cho phiếu seed chưa ghi;
# (6) khởi động lại ledger → log còn nguyên (kích thước cây không giảm, phiếu cũ vẫn xác minh), ghi tiếp
#     được với index nối tiếp.
# Phiếu nhập/xuất bất biến nên phiếu thử ở lại trong CSDL và sổ cái; số lượng nhập = xuất (tồn kho không đổi).
# Dùng: make up && make seed && bash scripts/smoke-ledger.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

KC="${KEYCLOAK_PUBLIC_URL:-http://localhost:8080}"
REALM="${KEYCLOAK_REALM:-disaster}"
GW="http://localhost:${APISIX_PORT:-9080}"
ADDR="http://127.0.0.1:${OPENBAO_PORT:-8200}"
DIR="${OPENBAO_LOCAL_DIR:-./.data/openbao}"
NET="${COMPOSE_PROJECT_NAME:-disaster-dxos}_default"
LEDGER_IMAGE=disaster-dxos/ledger:0.1.0
HANG=d0000000-0000-4000-8000-000000000004      # Mì tôm (seed)
PHIEU_SEED=e0000000-0000-4000-8000-000000000005  # phiếu seed, lúc đầu chưa ghi sổ
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail=0

check() { # check <tên> <mong đợi> <thực tế>
  if [ "$2" = "$3" ]; then echo "PASS  $1 → $3"; else echo "FAIL  $1 → $3 (mong đợi $2)"; fail=1; fi
}
get_token() { # get_token <username>
  curl -s -X POST "$KC/realms/$REALM/protocol/openid-connect/token" \
    -d grant_type=password -d client_id=dxos-dev-cli -d scope=openid \
    -d username="$1" --data-urlencode password="${KC_DEMO_USER_PASSWORD:?}" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
}
kv() { # kv <đường dẫn> <khóa>: đọc MỘT trường bí mật OpenBao bằng root token máy dev
  curl -s -K <(printf 'header = "X-Vault-Token: %s"\n' "$(cat "$DIR/root.token")") "$ADDR/v1/secret/data/$1" \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["data"]["data"].get(sys.argv[1], ""))' "$2"
}
# req <token|-> <tham số curl...>: in "<mã HTTP> <body>"; token đi qua file cấu hình curl
req() {
  local tok=$1 out code; shift
  out=$(mktemp)
  if [ "$tok" = - ]; then code=$(curl -s -o "$out" -w '%{http_code}' "$@")
  else code=$(curl -s -o "$out" -w '%{http_code}' -K <(printf 'header = "Authorization: Bearer %s"\n' "$tok") "$@"); fi
  printf '%s %s\n' "$code" "$(cat "$out")"
  rm -f "$out"
}
hc() { printf '%s' "${1%% *}"; }
# jf <biểu thức python trên d>: đọc phần body JSON (sau mã HTTP) từ stdin
jf() { python3 -c 'import sys,json; d=json.loads(sys.stdin.read().split(" ", 1)[1]); print(eval(sys.argv[1], {"d": d}))' "$1"; }
sql() { docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -q -v ON_ERROR_STOP=1'; }
lap() { # lap <token|-> <nhap|xuat> <số lượng> [ghi chú]
  req "$1" -X POST -H 'Content-Type: application/json' \
    -d "{\"supply_id\":\"$HANG\",\"direction\":\"$2\",\"quantity\":\"$3\",\"note\":\"${4:-Phiếu thử smoke #28}\"}" \
    "$GW/workflow/kho/phieu"
}
minh_bach() { req - "$GW/workflow/minh-bach/phieu/$1"; }
# verify_cli <index> <file bản ghi>: CLI kiểm chứng độc lập, chỉ thấy gateway (không mount bí mật/volume)
verify_cli() {
  docker run --rm -i --network "$NET" --entrypoint /ledger-verify "$LEDGER_IMAGE" \
    -log http://apisix:9080/ledger/ -verifier "$VK" -index "$1" -record - <"$2"
}
cp_size() { req - "$GW/ledger/checkpoint" | python3 -c 'import sys; print(sys.stdin.read().split(" ", 1)[1].split("\n")[1])'; }
# tamper <id> <delta>: sửa số lượng phiếu bằng superuser, vượt trigger bất biến (mô phỏng sửa trái phép CSDL)
tamper() {
  sql <<SQL >/dev/null
BEGIN;
ALTER TABLE cuu_tro.supply_movements DISABLE TRIGGER supply_movements_immutable;
UPDATE cuu_tro.supply_movements SET quantity = quantity + ($2) WHERE id = '$1';
ALTER TABLE cuu_tro.supply_movements ENABLE TRIGGER supply_movements_immutable;
COMMIT;
SQL
}

D=$(get_token dieuphoi01)
C=$(get_token cuuho01)

# ---------------- (1) Lõi: đọc công khai, chặn ghi từ ngoài ----------------
r=$(req - "$GW/ledger/verifier")
check "GET /ledger/verifier công khai (không token) → 200" 200 "$(hc "$r")"
VK=$(printf '%s' "${r#* }" | tr -d '\n')
check "khóa công khai trên gateway khớp verifier_key trong OpenBao" "$(kv core/ledger verifier_key)" "$VK"
ORIGIN=${VK%%+*}
r=$(req - "$GW/ledger/checkpoint")
check "GET /ledger/checkpoint công khai → 200" 200 "$(hc "$r")"
check "checkpoint mang origin của sổ cái" "$ORIGIN" "$(printf '%s' "${r#* }" | head -n1)"
check "checkpoint có chữ ký của khóa sổ cái" 1 "$(printf '%s' "${r#* }" | grep -c "^— $ORIGIN ")"
check "đọc .state/ của log qua gateway → 404" 404 "$(hc "$(req - "$GW/ledger/.state/treeState")")"
check "POST /ledger/entries qua gateway (không token) → 403" 403 \
  "$(hc "$(req - -X POST -H 'Content-Type: application/json' -d '{}' "$GW/ledger/entries")")"
check "POST /ledger/entries qua gateway (kèm JWT dieu-phoi) → 403" 403 \
  "$(hc "$(req "$D" -X POST -H 'Content-Type: application/json' -d '{}' "$GW/ledger/entries")")"
check "PUT /ledger/checkpoint qua gateway → 403" 403 "$(hc "$(req - -X PUT -d x "$GW/ledger/checkpoint")")"
check "ledger không mở cổng ra máy host (127.0.0.1:8090)" 000 \
  "$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:8090/healthz || true)"
noi_bo=$(docker compose exec -T cuu-tro-api python -c '
import httpx
b = {"type": "cuu-tro.phieu-kho", "ref": "smoke", "sha256": "0" * 64}
r1 = httpx.post("http://ledger:8090/ledger/entries", json=b)
r2 = httpx.post("http://ledger:8090/ledger/entries", json=b, headers={"Authorization": "Bearer sai-token"})
print(r1.status_code, r2.status_code)')
check "mạng nội bộ: POST ledger không token / sai token → 401" "401 401" "$noi_bo"
check "log của ledger không chứa khóa ký" 0 "$(docker compose logs ledger 2>&1 | grep -c 'PRIVATE+KEY' || true)"

# ---------------- (2) Lập 3 phiếu nhập/xuất ----------------
SIZE0=$(cp_size)
ID=() IDX=()
for spec in "nhap 10" "xuat 4" "xuat 6"; do
  # shellcheck disable=SC2086 # tách "chiều số_lượng" thành 2 tham số
  r=$(lap "$D" $spec)
  check "dieu-phoi lập phiếu ($spec) → 201" 201 "$(hc "$r")"
  check "phiếu ($spec) đã ghi sổ cái" da_ghi "$(jf 'd["so_cai"]["trang_thai"]' <<<"$r")"
  ID+=("$(jf 'd["ban_ghi_chuan_hoa"]["id"]' <<<"$r")")
  IDX+=("$(jf 'd["so_cai"]["index"]' <<<"$r")")
done
check "index 3 phiếu nối tiếp từ kích thước cây trước đó" "$SIZE0 $((SIZE0 + 1)) $((SIZE0 + 2))" "${IDX[*]}"
check "CSDL: 3 phiếu có ledger_index + leaf hash" "3" \
  "$(sql <<<"SELECT count(*) FROM cuu_tro.supply_movements WHERE id IN ('${ID[0]}','${ID[1]}','${ID[2]}') AND ledger_index IS NOT NULL AND octet_length(ledger_leaf_hash) = 32")"
check "CSDL: ledger_index khớp phản hồi API" "${IDX[*]}" \
  "$(sql <<<"SELECT string_agg(ledger_index::text, ' ' ORDER BY ledger_index) FROM cuu_tro.supply_movements WHERE id IN ('${ID[0]}','${ID[1]}','${ID[2]}')")"
check "cuu-ho lập phiếu → 403" 403 "$(hc "$(lap "$C" nhap 1)")"
check "không token lập phiếu → 401" 401 "$(hc "$(lap - nhap 1)")"
check "ghi chú có SĐT → 422 (ghi chú hiện công khai)" 422 "$(hc "$(lap "$D" nhap 1 'Người nhận 0905123456')")"
check "xuất quá tồn → 409" 409 "$(hc "$(lap "$D" xuat 999999)")"
gm='{"query":"mutation { insert_supply_movements_one(object: {}) { id } }"}'
check "GraphQL không còn đường lập phiếu (dieu-phoi)" validation-failed \
  "$(req "$D" -H 'Content-Type: application/json' -H 'X-Hasura-Role: dieu-phoi' -d "$gm" "$GW/graphql" | jf 'd["errors"][0]["extensions"]["code"]')"

# ---------------- (3) Trang công khai + CLI kiểm chứng độc lập ----------------
for i in 0 1 2; do
  r=$(minh_bach "${ID[$i]}")
  check "minh bạch phiếu $((i + 1)) (không đăng nhập) → đã xác minh" "200 da_xac_minh" "$(hc "$r") $(jf 'd["trang_thai"]' <<<"$r")"
done
check "trang công khai không lộ người lập phiếu" 0 "$(printf '%s' "$r" | grep -c 'dieuphoi01' || true)"
check "lá trên sổ cái không chứa người lập phiếu" False "$(jf '"dieuphoi01" in d["so_cai"]["la"]' <<<"$r")"
printf '%s' "${r#* }" >"$TMP/phieu3.json"
out=$(verify_cli "${IDX[2]}" "$TMP/phieu3.json" 2>&1) && code=0 || code=$?
check "ledger-verify độc lập (checkpoint + tile công khai) → mã 0" 0 "$code"
check "ledger-verify in ĐÃ XÁC MINH" 1 "$(grep -c 'ĐÃ XÁC MINH' <<<"$out" || true)"
# Khóa công khai khác, cùng tên sổ cái (kẻ giả mạo dựng sổ cái riêng) → không tin checkpoint
VK_THAT=$VK
VK=$(docker compose exec -T cuu-tro-api python -c '
import base64, hashlib, sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
pub = b"\x01" + Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
h = hashlib.sha256(sys.argv[1].encode() + b"\n" + pub).digest()[:4].hex()
print(f"{sys.argv[1]}+{h}+{base64.b64encode(pub).decode()}")' "$ORIGIN")
verify_cli "${IDX[2]}" "$TMP/phieu3.json" >"$TMP/cli.txt" 2>&1 && code=0 || code=$?
check "ledger-verify với khóa công khai lạ → mã 1 (chữ ký checkpoint sai)" "1 1" "$code $(grep -c 'checkpoint không xác minh được' "$TMP/cli.txt" || true)"
VK=$VK_THAT

# ---------------- (4) Sửa tay CSDL → không khớp ----------------
tamper "${ID[2]}" 1000
r=$(minh_bach "${ID[2]}")
check "sửa số lượng trong CSDL → trang công khai báo không khớp" khong_khop "$(jf 'd["trang_thai"]' <<<"$r")"
check "chi tiết nói rõ bản ghi đã bị sửa" True "$(jf 'any("đã bị sửa" in x for x in d["chi_tiet"])' <<<"$r")"
printf '%s' "${r#* }" >"$TMP/phieu3-sua.json"
verify_cli "${IDX[2]}" "$TMP/phieu3-sua.json" >"$TMP/cli.txt" 2>&1 && code=0 || code=$?
check "ledger-verify với bản ghi đã sửa → mã 1, KHÔNG KHỚP" "1 1" "$code $(grep -c 'KHÔNG KHỚP' "$TMP/cli.txt" || true)"
tamper "${ID[2]}" -1000
check "khôi phục bản ghi → lại đã xác minh" da_xac_minh "$(minh_bach "${ID[2]}" | jf 'd["trang_thai"]')"

# ---------------- (5) Chống trùng, ghi lại sổ ----------------
dup=$(docker compose exec -T cuu-tro-api python -c '
import asyncio, httpx, sys
from cuu_tro_workflow import api, so_cai
async def main():
    async with api.asyncpg.create_pool(open("/run/secrets/dxos/APP_DB_URL").read(), min_size=0, max_size=1) as pool:
        dong = await api.SoPhieu(pool).doc(sys.argv[1])
    tok = open("/run/secrets/dxos/LEDGER_WRITE_TOKEN").read().strip()
    r = httpx.post("http://ledger:8090/ledger/entries", json=so_cai.la_cho_phieu(so_cai.ban_ghi_chuan_hoa(dong)),
                   headers={"Authorization": f"Bearer {tok}"})
    print(r.status_code, r.json()["index"], r.json()["duplicate"])
asyncio.run(main())' "${ID[0]}")
check "gửi lại đúng lá của phiếu 1 → chống trùng trả index cũ" "200 ${IDX[0]} True" "$dup"
r=$(req "$D" -X POST -H 'Content-Type: application/json' -d '{}' "$GW/workflow/kho/phieu/$PHIEU_SEED/ghi-so")
check "ghi sổ phiếu seed (chưa ghi hoặc đã ghi lần trước) → 200 da_ghi" "200 da_ghi" "$(hc "$r") $(jf 'd["so_cai"]["trang_thai"]' <<<"$r")"
SEED_IDX=$(jf 'd["so_cai"]["index"]' <<<"$r")
check "gọi lại ghi sổ phiếu seed → cùng index" "$SEED_IDX" \
  "$(req "$D" -X POST -H 'Content-Type: application/json' -d '{}' "$GW/workflow/kho/phieu/$PHIEU_SEED/ghi-so" | jf 'd["so_cai"]["index"]')"
check "phiếu seed đã xác minh trên trang công khai" da_xac_minh "$(minh_bach "$PHIEU_SEED" | jf 'd["trang_thai"]')"

# ---------------- (6) Khởi động lại ledger: log còn, ghi tiếp được ----------------
SIZE1=$(cp_size)
docker compose restart ledger >/dev/null 2>&1
for _ in $(seq 1 30); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q ledger)")" = healthy ] && break
  sleep 2
done
check "ledger healthy sau khi khởi động lại" healthy "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q ledger)")"
check "kích thước cây giữ nguyên sau khởi động lại" "$SIZE1" "$(cp_size)"
check "phiếu cũ vẫn xác minh sau khởi động lại" da_xac_minh "$(minh_bach "${ID[0]}" | jf 'd["trang_thai"]')"
r=$(lap "$D" nhap 1)
check "ghi tiếp sau khởi động lại → index nối tiếp" "201 $SIZE1" "$(hc "$r") $(jf 'd["so_cai"]["index"]' <<<"$r")"
check "phiếu xuất cân lại tồn kho → 201" 201 "$(hc "$(lap "$D" xuat 1)")"

if [ "$fail" -ne 0 ]; then echo "smoke-ledger: CÓ LỖI"; exit 1; fi
echo "smoke-ledger: tất cả đều đạt"
