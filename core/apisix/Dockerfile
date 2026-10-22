# SPDX-License-Identifier: Apache-2.0
# Image APISIX của Disaster DX-OS = image gốc apache/apisix + file coraza-proxy-wasm phát hành chính thức (#12).
# Không chép mã nguồn Coraza vào repo: tải bản .zip của GitHub Release, kiểm SHA-256 rồi mới dùng.
# OWASP CRS v4 đã nhúng sẵn trong file .wasm (gọi bằng "Include @owasp_crs/*.conf").
# Nâng phiên bản: đổi CORAZA_WASM_VERSION + CORAZA_WASM_SHA256 (digest asset trên trang Release),
# cập nhật DEPENDENCIES.md và NOTICE.

ARG APISIX_IMAGE=apache/apisix:3.19.0-debian

FROM alpine:3.22.2 AS coraza
ARG CORAZA_WASM_VERSION=0.6.0
ARG CORAZA_WASM_SHA256=cca4e3c75cf6b2e615907f936a1b6dcd0955250e0fb7d3b1c2ecef807d84603c
WORKDIR /dl
RUN wget -q -O coraza.zip \
      "https://github.com/corazawaf/coraza-proxy-wasm/releases/download/${CORAZA_WASM_VERSION}/coraza-proxy-wasm-${CORAZA_WASM_VERSION}.zip" \
 && echo "${CORAZA_WASM_SHA256}  coraza.zip" | sha256sum -c - \
 && unzip -q coraza.zip coraza-proxy-wasm.wasm

FROM ${APISIX_IMAGE}
COPY --from=coraza /dl/coraza-proxy-wasm.wasm /usr/local/apisix/wasm/coraza-proxy-wasm.wasm
