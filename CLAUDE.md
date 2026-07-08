# Hetairoi — agent orientation

Hetairoi is the **event-driven scenario layer** over an
[ahsir](https://github.com/wu8685/ahsir) agent fleet. It watches external sources
(GitHub issues/PRs, CodeHub, work items), matches events with declarative handlers,
and **dispatches ahsir agents to act** — creating sessions and running turns on
ahsir's CMA API through the official `anthropic-sdk-go`. It is a CMA **client**, not
a CMA server: agents, sessions, and their state live on the ahsir facade, not here.

(The CMA gateway used to live in this repo; it moved into ahsir — see
`docs/RFC-001-cma-gateway-into-ahsir.md` for that history.)

**Read first:** `docs/DESIGN.md` (architecture + rationale), `docs/EVENTBUS-SPEC.md`
(the policy model), `docs/EVENTBUS-SOURCES.md` (sources + control plane). `README.md`
is the value pitch.

## Repo map

```
cmd/hetairoi/       entrypoint: wire the SDK driver + eventbus, serve the control plane
internal/sdkdriver/ eventbus.SessionDriver on the official anthropic-sdk-go
                    (Sessions.New / Events.Send / StreamEvents / List) → drives ahsir's CMA facade
internal/eventbus/  sources + handlers/policies + bus + registry + webhook — the core
internal/api/       slim HTTP: eventbus admin (/v1/eventbus/{sources,handlers}) + webhook (/eventbus/events) + auth
internal/config/    Listen / APIKeys / StateFile
```

The seam between the two halves is `eventbus.SessionDriver`
(`CreateSession / SendUserMessage / RunForReply / SessionSummary`) — the eventbus is
runtime-agnostic; `internal/sdkdriver` is the only implementation, backed by the SDK.

## Topology (deployed)

```
ahsir:  scheduler :9800  +  CMA facade :18790
Hetairoi:  eventbus-only :18791  ──CMA_FACADE_URL──▶ ahsir facade :18790  (official SDK)
```

Both run as login LaunchAgents under `~/.cma-stack/` (see the project memory).

## Build / test (this machine)

- Module is inside `GOPATH/src` with `GO111MODULE=off` global → **prefix with `GO111MODULE=on`**.
- This Mac **SIGKILLs directly-run freshly-built binaries** → use `go run`, or codesign the binary (`codesign --force --sign - <bin>`) before running it.

```sh
GO111MODULE=on go build ./...
GO111MODULE=on go vet ./...
GO111MODULE=on go test -short ./...     # unit; the sdkdriver integration test is -short/env-gated
CMA_FACADE_URL=http://127.0.0.1:18790 CMA_LISTEN=127.0.0.1:18791 \
  GO111MODULE=on go run ./cmd/hetairoi
```

The full-path check is `internal/sdkdriver/driver_integration_test.go`: it boots a
real `ahsir start --cma-listen` (echo provider) and drives the SDK `SessionDriver`
against it end to end.

## Constraints that matter

1. **It's a CMA client, not a server.** Agents/environments/sessions live on the
   ahsir facade. Hetairoi never owns agent state; don't reintroduce a local store or
   the `/v1/{agents,environments,sessions}` routes — those are ahsir's now.
2. **The SDK driver is the only path to ahsir.** All fleet interaction goes through
   `internal/sdkdriver` (official `anthropic-sdk-go` → `CMA_FACADE_URL`). This
   dogfoods ahsir's CMA API; keep it that way.
3. **The eventbus is the core.** Sources/handlers/policies/dedup/persistence in
   `internal/eventbus`. New capability is usually a new source or policy, not a new
   HTTP surface.
4. **Deploy + restart order.** Rebuild `~/.cma-stack/bin/hetairoi` + codesign, then
   `bootout`+`bootstrap` `com.wu8685.hetairoi`. If you ever restart the whole stack,
   bring cma-stack ports up so ahsir binds `:18790` before Hetairoi points at it.
5. **`CMA_*` env prefix is intentional.** Hetairoi *is* a CMA client, so
   `CMA_FACADE_URL` / `CMA_API_KEY` read correctly; the prefix was kept on purpose.

## Current status

Migration complete: the CMA gateway lives in ahsir; Hetairoi is eventbus +
official-SDK-client only. Live-validated end to end — labeling a GitHub issue
`agent-build` drove the full autonomous dev loop (coder → PR → reviewer → verdict)
through the new architecture. See `docs/ROADMAP.md`.
