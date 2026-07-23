# Hetairoi — Status & Roadmap

## Current status (2026-07-08)

**Migration complete. Hetairoi is the eventbus + official-SDK-client scenario layer;
the CMA gateway now lives in ahsir.** Live-validated end to end: labeling a GitHub
issue `agent-build` drove the full autonomous dev loop — a coder agent implemented
it, opened a PR, and a reviewer agent built/tested and posted a verdict — all through
the new architecture (Hetairoi eventbus → SDK driver → ahsir CMA facade → agents).

What runs today:

- **Eventbus core** — sources (GitHub / CodeHub / workitem poll + inbound webhook),
  declarative handlers, `stateless` / `keyed` / `routed` policies, dedup by event id,
  per-handler JSON persistence, per-session serial turns, and the dynamic control
  plane (`/v1/eventbus/{sources,handlers}`). See EVENTBUS-SPEC / EVENTBUS-SOURCES.
- **SDK driver** — `internal/sdkdriver` implements `eventbus.SessionDriver` on the
  official `anthropic-sdk-go`, driving ahsir's CMA facade. Checked by
  `internal/sdkdriver/driver_integration_test.go` (boots a real ahsir with an `echo`
  provider and exercises all four driver methods).
- **Flagship scenario** — the autonomous dev loop (coder → PR → reviewer → verdict,
  human-merge gate). Wiring recipe: `tools/DEV-LOOP-PLAYBOOK.md` /
  `tools/setup-dev-loop.py`.

## How we got here

The CMA gateway used to live in this repo. It was migrated **into ahsir** so ahsir
speaks CMA natively, and this repo became a pure CMA client. Phases (all done):

- **P1** — stood up the CMA facade inside ahsir; verified with the native Python SDK.
- **P2** — reimplemented `eventbus.SessionDriver` on the official Go SDK (dogfood).
- **P3** — cut the running stack over (ahsir facade `:18790`, Hetairoi eventbus
  `:18791`), then deleted the now-dead in-process gateway (`internal/{cma,translate,
  store,ahsir}`, the CMA handlers, the old gateway e2e) — Hetairoi is SDK-only.
- **Rename** — `cma-service` → **Hetairoi**.

Full design/history: `docs/RFC-001-cma-gateway-into-ahsir.md`.

## Open follow-ups / notes

- **`~/.cma-stack/` deploy dir** still carries the old "cma stack" name (shared with
  ahsir). Renaming it has a wide blast radius (every plist/token/path) — deferred.
- **`CMA_*` env prefix kept on purpose** — Hetairoi *is* a CMA client, so
  `CMA_FACADE_URL` / `CMA_API_KEY` read correctly.
- **Eventbus reliability** — an ordinary GitHub fetch failure leaves the in-memory
  `since` watermark unchanged, so the next polling interval retries that window
  without dispatching a partial result. Restart downtime remains unresolved: the
  source starts from `now`, and reconciliation/event-log recovery is still separate
  follow-up work.
- **Richer scenarios** — beyond the dev loop, the eventbus supports triage/routing
  patterns; new capability is usually a new source or policy, not new HTTP surface.

## Local dev notes (this machine)

- Module in `GOPATH/src` with `GO111MODULE=off` global → prefix `GO111MODULE=on`.
- Freshly-built binaries are SIGKILLed unless codesigned → `go run`, or
  `codesign --force --sign - <bin>` before running.
- Deploy: rebuild `~/.cma-stack/bin/hetairoi` + codesign, then `bootout`+`bootstrap`
  `com.wu8685.hetairoi`. Env: `CMA_LISTEN` (`:18791`), `CMA_FACADE_URL`
  (`http://127.0.0.1:18790`, required), `CMA_API_KEY`, `CMA_STATE_FILE`.
