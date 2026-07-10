# Multi-agent dev loop — playbook (issue → code → PR → review → fix → merge)

Reproducible recipe for the autonomous coding loop. Built + validated 2026-07-03
against `wu8685/ahsir` (issue #1 → PR #2 → reviewer APPROVED, all autonomous).
Goal of this doc: spin the **same formation** back up fast, without re-hitting the
gotchas below.

## Stack it runs on
- hetairoi eventbus `127.0.0.1:18791`, ahsir CMA facade `:18790`, ahsir scheduler
  `:9800`, ahsir UI `:19801` — all login LaunchAgents under `~/.cma-stack/` (see the
  hetairoi-autostart memory). hetairoi drives the facade over the official CMA SDK;
  `setup-dev-loop.py` is two-port (CMA calls → facade :18790, eventbus wiring → :18791).
- The `github` eventbus source lives in hetairoi (`internal/eventbus/source_github.go`,
  3-event model). Rebuild the deployed binary after code changes:
  `GO111MODULE=on go build -o ~/.cma-stack/bin/hetairoi ./cmd/hetairoi && codesign --force --sign - ~/.cma-stack/bin/hetairoi && launchctl kickstart -k gui/501/com.wu8685.hetairoi`

## The formation (what setup-dev-loop.py creates)
- **agents** (opus, `metadata.shell_access=true`, `runtime_timeout` 1800–2400s):
  `ahsir-coder` (implement/fix, push, open PR), `ahsir-reviewer` (build/test + verdict comment).
  **Symmetric test-coverage duty:** the coder MUST ship tests that exercise its own new/changed
  logic (verified via `go test -coverprofile` before pushing; untested logic = don't open the PR).
  The reviewer's remit explicitly includes **test-coverage adequacy** — not just "tests pass" but
  that the PR adds tests exercising the new/changed behavior (measured via `go test -coverprofile`
  + `go tool cover -func`); missing tests on new logic ⇒ `changes` verdict. Pure-UI changes are
  flagged as out-of-headless-scope for a human / Playwright ui-verify.
- **handlers** (keyed, **repo-qualified keys**): `ahsir-build` (`type=issue` + `authorized=true` → coder,
  key `{{.payload.repo}}#issue-{{.subject}}`; `authorized` is the owner-backed approval gate — an
  `agent-build` label alone does NOT start work, see the trust boundary in `docs/EVENTBUS-SOURCES.md`),
  `ahsir-review` (`type=pr.push` + `is_agent_pr=true` → reviewer, key `{{.payload.repo}}#pr-{{.subject}}`),
  `ahsir-fix` (`type=pr.review` + `review_verdict=changes` → coder, key `{{.payload.repo}}#issue-{{.payload.issue_ref}}` — same session as build).
  **Why repo-qualified:** the loop now watches more than one repo (below), and a bare `issue-{{.subject}}`
  would collide two repos' issue #N onto one keyed session. build↔fix share a key so the coder that
  built an issue also fixes it, with context.
- **sources** — one `github` source **per watched repo** (`WATCH_REPOS` in the script), e.g.
  `gh-ahsir-loop` → `wu8685/ahsir` and `gh-hetairoi-loop` → `wu8685/hetairoi` (each `kinds=both`,
  `interval=2m`, `token_file=~/.cma-stack/github-token`). Handlers are repo-agnostic (match on event
  TYPE + template on `{{.payload.repo}}`), so one coder/reviewer serves every repo — the loop dogfoods
  itself by watching its own repos. (Validated 2026-07-10, end-to-end unattended on both repos.)
- **NO** `approved` handler → reviewer's `approved` verdict HALTS the loop for human merge.

## Run it
```sh
# 0. ensure the 3-event source is in the deployed binary (rebuild+restart if source_github.go changed)
# 1. verify PAT write scope on the target repo (avoids a wasted 403 turn):
#    create+delete a temp branch ref via the API (Contents:write); Issues+PR write also needed.
# 2. create the formation (edit WATCH_REPOS at top of the script to watch different/more repos):
python3 ~/.cma-stack/tools/setup-dev-loop.py
# 3. kick off: as the repo OWNER, open an issue with the `agent-build` label (or, on a
#    non-owner issue, post an owner `<!-- cma-approve -->` comment). The 2m poll picks it up.
# 4. watch: GitHub PR list, ahsir UI :19801, or `tail -f ~/.cma-stack/logs/ahsir.err`.
```
Pause the loop (keeps handlers/agents): `curl -s --noproxy '*' -X DELETE http://127.0.0.1:18791/v1/eventbus/sources/gh-ahsir-loop`

## Gotchas (the expensive-to-rediscover ones)
1. **Loopback proxy.** This box has `http_proxy=127.0.0.1:7897`; loopback dies unless
   `export no_proxy=127.0.0.1,localhost` per process and `curl --noproxy '*'`. **The daemon
   inherits that proxy from launchd's global env** — and routing `api.github.com` through the flaky
   7897 proxy makes every GitHub poll fail with `... : EOF` (whole loop silently idle). Fix: the
   hetairoi plist `no_proxy` MUST include `github.com,api.github.com` so GitHub goes direct (verified:
   direct returns 200, the proxy EOFs). Env change needs `bootout`+`bootstrap` (not kickstart).
   Diagnose with `ps eww <pid> | tr ' ' '\n' | grep -i proxy`.
2. **Single GitHub account can't self-approve.** GitHub blocks approve/request-changes
   on your OWN account's PR. So routing is by **event type** (coder⇒`pr.push`, reviewer⇒`pr.review`)
   + a **verdict marker in a PR comment** (`<!-- cma-review:approved -->` / `<!-- cma-review:changes -->`),
   NOT native review state. Event-type separation also prevents self-triggering.
3. **CMA_TURN_TIMEOUT default 10m is too short** for real coding turns → set `CMA_TURN_TIMEOUT=45m`
   in the hetairoi plist + `runtime_timeout` (e.g. 2400s) on the agent. Changing plist env
   needs `launchctl bootout gui/501/<label>` then `bootstrap` (kickstart does NOT reload env).
4. **PAT scope.** Fine-grained token needs the target repo with Contents + Pull requests + Issues
   write. Probe first: create+delete a temp ref (Contents:write); a read-only token 403s on the first push.
5. **merged ≠ deployed.** The loop clones the GitHub repo; the running ahsir stack is built from
   local `~/workspace/.../ahsir`. Merging to GitHub main does NOT change the running scheduler/UI —
   rebuild `~/.cma-stack/bin/{ahsir,ahsir-agent}` from the updated source + restart to deploy.
6. **Stale handlers conflict.** A handler matching `type=issue` with no label filter will intercept
   the new repo's issues. Delete old repo-specific handlers before wiring a new repo's loop.
7. **Re-trigger a handled issue**: toggle its label (remove+re-add `agent-build`) → bumps updated_at
   → new Event.ID → re-fires. Dedup is per Event.ID (persisted in `~/.cma-stack/eventbus/<handler>.json`).
   Source `since` starts at `now` on (re)start, so it never replays history — only new activity fires.
   **CAVEAT:** if the issue's NEWEST comment carries the bot marker (e.g. the agent's own
   "Opened PR #N `<!-- cma-agent -->`"), the issue marker-guard suppresses the event and the label
   toggle does nothing — post a NON-marker comment (or delete the marked one) to re-trigger. (A stale
   keyed binding to a deleted session is fine: the bus checks `alive(sid)` and creates a fresh one.)
8. **UI verification is part of the reviewer's job (v3+).** The reviewer's prompt makes it run a
   headless UI smoke for any `internal/ui/`/frontend diff: `python3 ~/.cma-stack/tools/ui-smoke.py
   <owner/repo> <branch> <out.png>` — builds the branch, runs an isolated scheduler+UI, loads the
   console in Playwright's bundled chromium (system Chrome headless HANGS on this box; Playwright is
   ~2s reliable), and returns `pass` + `console_errors` + a screenshot. The reviewer folds PASS/FAIL
   into its verdict (JS errors / blank page ⇒ `changes`). **Honest limit:** it's a *functional* smoke —
   the reviewer can act on PASS/FAIL text but CANNOT see the screenshot, so visual layout / feature
   correctness still needs a human eye. `ui-verify.py` is the richer variant (seeds state + drives a
   click-through) for feature-specific checks.
9. **ahsir agent transcripts survive deletion** (`.a2a/transcripts/*.jsonl`, per-completed-turn), but the
   UI only lists registered agents. To view a deleted agent: re-register via `POST /admin/agents`
   `{name, workspace}` (no card → reuses the existing workspace, no re-scaffold). 30-day retention
   (`CompactForRetention` at agent startup) prunes older transcripts. (PR #2 added an "Archived" UI for this.)

10. **Idle-reaper self-starvation (FIXED ahsir #20, deployed 2026-07-10).** The scheduler scales an
    agent runtime to zero after `agent_idle_timeout=10m` idle. An event-driven loop is idle >10m
    between bursts almost by definition, so the FIRST dispatch after any quiet period used to hit a
    dead cached port → `dial 127.0.0.1:<port>: connection refused` → session terminal. The reviewer
    (long gaps between PRs) was hit worst — every review died. Fix: `handleA2AProxy` now calls
    `ensureAwake` before dialing, so a scaled-to-zero runtime re-spawns. Deployed-log signature of a
    healthy wake: `idle-stopped → waking from idle-stopped → awake and healthy → <turn>`, zero
    `connection refused`. If you see terminated sessions right after an idle period on an OLD binary,
    this is why — redeploy. (Before the fix, the workaround was `bootout+bootstrap com.wu8685.ahsir`
    to cold-start, or keeping the runtime warm with back-to-back turns <10m apart.)
11. **git push through the proxy times out.** `wu8685/hetairoi`'s origin is **HTTPS** → pushes via the
    7897 proxy fail `Recv failure: Operation timed out` (fetch sometimes squeaks through, push won't).
    `wu8685/ahsir` is SSH. **Push over SSH regardless:** `git push git@github.com:wu8685/<repo>.git HEAD:<branch>`.
12. **Deploy procedure (validated 2026-07-10).** Build straight to the deployed path + codesign (this
    Mac SIGKILLs unsigned fresh binaries), then `bootout`+`bootstrap`. Order: **ahsir first** (owns
    facade :18790), then hetairoi. ahsir's UI and scheduler share ONE `ahsir` binary (rebuild updates
    both); `ahsir-agent` is a separate build. hetairoi runtime config (sources/handlers) persists in
    `~/.cma-stack/eventbus/_registry.json` across restarts — it is NOT reset by a redeploy, so re-run
    `setup-dev-loop.py` only when you intend to rebuild the formation.

13. **Concurrent-safe agents (#18 instances / #19 session_isolation — reachable from facade since #25).**
    By default one agent card = one runtime = one shared workspace, so two issues dispatched at once
    make their coder sessions clobber each other's working tree — which is why multi-issue batches must
    run **strictly sequentially** today. To lift that, set on the agent's `metadata` at creation:
    `session_isolation: "worktree"` (per-session git worktree; **falls back to `scratch` per-session
    dirs when the agent's workspace is not a git repo** — the loop's coder workspace isn't, so it gets
    scratch, still collision-free) and/or `instances: "2"` (scheduler pools up to N isolated-workspace
    instances, spawned on demand). The facade forwards both into the spawned agent's card /
    `AgentConfig` (`internal/cmagateway/translate`). Validated 2026-07-10: a probe agent with
    `instances=2, session_isolation=worktree` spawned with `pool.session_isolation: worktree` in its
    card and ran two concurrent sessions under `Session isolation: mode=scratch` (worktree→scratch
    fallback, no git workspace). `setup-dev-loop.py` still creates single-instance coder/reviewer — add
    the two metadata keys there if you want the loop to process issues in parallel.

## Cost/safety
- Each coder/reviewer turn ≈ a multi-minute opus turn ($). A full loop = several turns.
- Guards: `agent-build` label gate, optional `allow_numbers` on the source, the 5-round self-cap in
  the coder prompt, and the human merge gate. Keep the source paused when not actively using it.
