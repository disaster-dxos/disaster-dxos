#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Tạo hoặc cập nhật client Keycloak "dxos-grafana" (SSO cho Grafana, #126) trong realm KEYCLOAK_REALM.
# Realm chỉ import khi CSDL Keycloak còn trống (--import-realm bỏ qua realm đã có), nên client của dịch vụ
# lõi không đặt trong apps/<app>/keycloak/realm.json mà thêm bằng script này, chạy mỗi lần bật profile bi
# (container một lần keycloak-grafana-client, image Keycloak gốc, dùng kcadm.sh). Chạy lại bao nhiêu lần cũng
# được: chưa có thì tạo, có rồi thì ghi đè cấu hình + secret theo OpenBao, thêm mapper còn thiếu.
# Áp được cho mọi ứng dụng (realm của apps/muon-thiet-bi cũng nhận client này).
# Vào:  /run/secrets/dxos/KC_BOOTSTRAP_ADMIN_PASSWORD, KC_GRAFANA_CLIENT_SECRET (bao-agent-keycloak render)
#       /opt/dxos/keycloak/grafana-client.json, grafana-roles-mapper.json (core/keycloak/)
# Biến: KEYCLOAK_URL (http://keycloak:8080), KEYCLOAK_REALM, KC_BOOTSTRAP_ADMIN_USERNAME, GATEWAY_PUBLIC_URL.
# Image Keycloak không có sed/jq/python: thay placeholder bằng bash.
set -euo pipefail

SECRETS=${SECRETS_DIR:-/run/secrets/dxos}
DEF=${CLIENT_DEF_DIR:-/opt/dxos/keycloak}
REALM=${KEYCLOAK_REALM:-disaster}
KC=${KEYCLOAK_URL:-http://keycloak:8080}
CLIENT_ID=dxos-grafana
kcadm() { /opt/keycloak/bin/kcadm.sh "$@" --config /tmp/kcadm.config; }
log() { echo "keycloak-grafana-client: $*"; }

# Đợi bao agent render secret client (máy cũ: openbao-init vừa thêm secret/core/grafana-oauth)
for _ in $(seq 1 60); do [ -s "$SECRETS/KC_GRAFANA_CLIENT_SECRET" ] && break; sleep 2; done
[ -s "$SECRETS/KC_GRAFANA_CLIENT_SECRET" ] || { log "chưa có KC_GRAFANA_CLIENT_SECRET. Chạy: make bao-init"; exit 1; }
secret=$(<"$SECRETS/KC_GRAFANA_CLIENT_SECRET")
[[ $secret =~ ^[A-Za-z0-9]+$ ]] || { log "KC_GRAFANA_CLIENT_SECRET có ký tự lạ"; exit 1; }
gw=${GATEWAY_PUBLIC_URL:?}
gw=${gw%/}

client=$(<"$DEF/grafana-client.json")
d='$'  # placeholder ${TÊN} trong tệp JSON, thay bằng chuỗi (không expand)
client=${client//"$d{KC_GRAFANA_CLIENT_SECRET}"/$secret}
client=${client//"$d{GATEWAY_PUBLIC_URL}"/$gw}
mapper=$(<"$DEF/grafana-roles-mapper.json")
mapper_name=dxos-realm-roles

kcadm config credentials --server "$KC" --realm master \
  --user "${KC_BOOTSTRAP_ADMIN_USERNAME:-admin}" --password "$(<"$SECRETS/KC_BOOTSTRAP_ADMIN_PASSWORD")" >/dev/null

id=$(kcadm get clients -r "$REALM" -q "clientId=$CLIENT_ID" --fields id --format csv --noquotes)
if [ -z "$id" ]; then
  kcadm create clients -r "$REALM" -f - <<<"$client" >/dev/null
  id=$(kcadm get clients -r "$REALM" -q "clientId=$CLIENT_ID" --fields id --format csv --noquotes)
  log "đã tạo client $CLIENT_ID trong realm $REALM"
else
  kcadm update "clients/$id" -r "$REALM" -f - <<<"$client"
  log "client $CLIENT_ID đã có trong realm $REALM: đã cập nhật cấu hình + secret"
fi

names=$(kcadm get "clients/$id/protocol-mappers/models" -r "$REALM" --fields name --format csv --noquotes)
if [[ $'\n'$names$'\n' == *$'\n'$mapper_name$'\n'* ]]; then
  log "mapper $mapper_name: đã có"
else
  kcadm create "clients/$id/protocol-mappers/models" -r "$REALM" -f - <<<"$mapper" >/dev/null
  log "mapper $mapper_name: đã tạo (claim roles = vai realm, trong id token + userinfo)"
fi
rm -f /tmp/kcadm.config
