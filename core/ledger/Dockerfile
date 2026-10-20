# SPDX-License-Identifier: Apache-2.0
# Image dịch vụ sổ cái core/ledger (#28): build từ mã nguồn trong repo (Go + Tessera qua go.mod),
# image chạy là "scratch" chỉ có 2 file nhị phân tĩnh: ledger (dịch vụ) và ledger-verify (CLI kiểm
# chứng độc lập). Image Go chỉ dùng ở bước build. Không có shell: healthcheck gọi "ledger healthcheck".
# Nâng Go: đổi GO_IMAGE (cùng dòng với "go" trong go.mod), cập nhật DEPENDENCIES.md.

ARG GO_IMAGE=golang:1.26.10-alpine3.24

FROM ${GO_IMAGE} AS build
WORKDIR /src
ENV CGO_ENABLED=0 GOFLAGS=-trimpath GOTOOLCHAIN=local
COPY . .
# Cache module/build của BuildKit (không nằm trong image); go build kiểm go.sum cho mọi module tải về
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    go build -ldflags="-s -w" -o /out/ledger ./cmd/ledger \
 && go build -ldflags="-s -w" -o /out/ledger-verify ./cmd/ledger-verify \
 && mkdir -p /out/data/log /out/data/antispam

FROM scratch
COPY --from=build /out/ledger /out/ledger-verify /
# Volume ledgerdata lần đầu nhận quyền sở hữu của /data trong image (uid 65532, không phải root)
COPY --from=build --chown=65532:65532 /out/data /data
USER 65532:65532
EXPOSE 8090
ENTRYPOINT ["/ledger"]
