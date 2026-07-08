# Hetairoi — agent orientation (Codex)

Equivalent to `CLAUDE.md`; kept in sync for Codex.

**What this is:** the **event-driven scenario layer** over an
[ahsir](https://github.com/wu8685/ahsir) agent fleet. It watches external sources
(GitHub issues/PRs, CodeHub, work items), matches events with declarative handlers,
and **dispatches ahsir agents** — creating sessions and running turns on ahsir's CMA
API via the official `anthropic-sdk-go`. It is a CMA **client**, not a server: agents
and sessions live on the ahsir facade, not here. (The CMA gateway used to live in this
repo; it moved into ahsir — see `docs/RFC-001-cma-gateway-into-ahsir.md`.)

**Read first:** `docs/DESIGN.md`, `docs/EVENTBUS-SPEC.md`, `docs/EVENTBUS-SOURCES.md`.

## Repo map

```
cmd/hetairoi/       entrypoint: wire the SDK driver + eventbus, serve the control plane
internal/sdkdriver/ eventbus.SessionDriver on the official anthropic-sdk-go → ahsir's CMA facade
internal/eventbus/  sources + handlers/policies + bus + registry + webhook — the core
internal/api/       slim HTTP: eventbus admin (/v1/eventbus/{sources,handlers}) + webhook + auth
internal/config/    Listen / APIKeys / StateFile
```

Seam: `eventbus.SessionDriver` (`CreateSession / SendUserMessage / RunForReply /
SessionSummary`) — the eventbus is runtime-agnostic; `internal/sdkdriver` is the only
implementation.

## Topology (deployed)

```
ahsir:  scheduler :9800 + CMA facade :18790
Hetairoi:  eventbus-only :18791 ──CMA_FACADE_URL──▶ ahsir facade :18790  (official SDK)
```

Both run as login LaunchAgents under `~/.cma-stack/`.

## Build / test (this machine)

- Module in `GOPATH/src` with `GO111MODULE=off` global → **prefix with `GO111MODULE=on`**.
- This Mac **SIGKILLs directly-run freshly-built binaries** → use `go run`, or codesign before running.

```sh
GO111MODULE=on go build ./...
GO111MODULE=on go vet ./...
GO111MODULE=on go test -short ./...     # unit; sdkdriver integration test is -short/env-gated
CMA_FACADE_URL=http://127.0.0.1:18790 CMA_LISTEN=127.0.0.1:18791 \
  GO111MODULE=on go run ./cmd/hetairoi
```

## Constraints

1. **CMA client, not server** — agents/sessions live on the ahsir facade; don't
   reintroduce a local store or the `/v1/{agents,environments,sessions}` routes.
2. **The SDK driver is the only path to ahsir** — all fleet interaction via
   `internal/sdkdriver` (official `anthropic-sdk-go` → `CMA_FACADE_URL`).
3. **The eventbus is the core** — new capability is usually a new source or policy.
4. **`CMA_*` env prefix is intentional** — Hetairoi is a CMA client.

## Status

Migration complete: CMA gateway now in ahsir; Hetairoi is eventbus + official-SDK-client
only. Live-validated end to end (autonomous dev loop: coder → PR → reviewer → verdict).
See `docs/ROADMAP.md`.
