Tiếng Việt (full documentation): [README.md](README.md)

![Disaster DX-OS: rescue teams, water-level sensors and a coordination post in a flooded village](docs/images/banner.webp)

# Disaster DX-OS

**An open-source operating system for disaster response and community relief.** Local authorities, rescue teams and volunteers triage distress calls, dispatch the nearest available team, and publish relief supply movements in an append-only ledger that anyone can verify.

[![License Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Release](https://img.shields.io/github/v/release/disaster-dxos/disaster-dxos)](https://github.com/disaster-dxos/disaster-dxos/releases)
[![CI](https://github.com/disaster-dxos/disaster-dxos/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/disaster-dxos/disaster-dxos/actions/workflows/ci.yml)

Entry for the Vietnam OLP Open Source Software contest 2026 (DX-OS Open-Core track), team DTU_DZ_1. Code comments and full docs are in Vietnamese.

## Architecture

![Architecture: the apps/cuu-tro application (Tier 2) calls the headless core (Tier 1) only through the APISIX gateway](docs/images/kien-truc.svg)

- **Tier 1, headless core** (`core/`, API only, no business logic): Keycloak (SSO/MFA), Apache APISIX + Coraza WAF (API gateway), PostgreSQL + PostGIS with Hasura CE GraphQL (structured data), SeaweedFS S3 (unstructured data), Temporal (workflow engine), NATS JetStream + MQTT, a Tessera transparency log (`core/ledger`, Go) and OpenBao for secrets.
- **Tier 2, application** (`apps/cuu-tro/`): realm and roles, PostGIS schema with mistake-proofing constraints, GraphQL permissions, Python backend (dispatch workflow, sensor consumer, field photos, supply ledger). The Nuxt web console and Flutter field app are in progress.

![Main flows: distress call to dispatch to confirmation, and supply voucher to ledger to public verification](docs/images/luong-cuu-tro.svg)

Details (Vietnamese): [`docs/architecture.md`](docs/architecture.md).

## Quick start

Requires Docker with Compose 2.20+, about 4 GB RAM for Docker, 10 GB free disk, plus `git`, `make`, `bash`, `curl`, `python3`, `openssl`.

```bash
git clone https://github.com/disaster-dxos/disaster-dxos.git
cd disaster-dxos
cp .env.example .env
make up      # initialises and unseals OpenBao, generates all core secrets, starts core + app
make smoke   # 339 end-to-end checks through the gateway and the database
```

Measured from a fresh clone on 22 Oct 2026 (Apple Silicon Mac, no cached images): first `make up` 2 min 36 s, `make smoke` 72 s, 339/339 passed. Unseal keys go to `.data/openbao/` (git-ignored): keep it private. If token requests from the host fail with "HTTPS required", see the troubleshooting table in [README.md](README.md#xử-lý-lỗi-thường-gặp).

Sample users `dieuphoi01`, `cuuho01`, `tinhnguyen01` (fake data, password `KC_DEMO_USER_PASSWORD` in `.env`). Gateway: `http://localhost:9080`, Keycloak: `http://localhost:8080`.

## License

[Apache-2.0](LICENSE). Third-party notices: [`NOTICE`](NOTICE), component versions and licenses: [`DEPENDENCIES.md`](DEPENDENCIES.md). Copyleft components run as separate, unmodified upstream images. Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md). Changes: [`CHANGELOG.md`](CHANGELOG.md).
