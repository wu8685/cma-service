#!/usr/bin/env python3
"""ui-smoke: generic headless UI smoke for a PR branch — build it, run an isolated
ahsir scheduler+UI, load the console in Playwright's chromium, and report whether
the page renders with ZERO JS console/page errors, plus a screenshot. Purely
functional (renders + no crash); it does NOT judge visual/aesthetic correctness.

Usage: ui-smoke.py <owner/repo> <branch> [out.png]
Exit 0 = PASS (page rendered, no console errors); 1 = FAIL.
"""
import os, sys, json, shutil, subprocess, tempfile, time, pathlib

REPO   = sys.argv[1] if len(sys.argv) > 1 else "wu8685/ahsir"
BRANCH = sys.argv[2] if len(sys.argv) > 2 else "main"
OUT    = sys.argv[3] if len(sys.argv) > 3 else "/tmp/ui-smoke.png"
TOKEN_FILE = os.path.expanduser("~/.cma-stack/github-token")
GO = "/usr/local/go/bin/go"
ENV = {**os.environ, "no_proxy": "127.0.0.1,localhost", "NO_PROXY": "127.0.0.1,localhost",
       "GO111MODULE": "on", "AHSIR_ADMIN_TOKEN": "ui-smoke-token"}
SCHED_PORT, UI_PORT = 29940, 29941

work = tempfile.mkdtemp(prefix="ui-smoke-"); procs = []
def teardown():
    for p in procs:
        try: p.terminate()
        except Exception: pass
    time.sleep(1)
    subprocess.run(["pkill", "-f", f"registry http://127.0.0.1:{SCHED_PORT}"], env=ENV)
    shutil.rmtree(work, ignore_errors=True)

try:
    tok = pathlib.Path(TOKEN_FILE).read_text().strip()
    subprocess.run(["git","clone","--depth","1","-b",BRANCH,
                    f"https://x-access-token:{tok}@github.com/{REPO}.git", f"{work}/src"],
                   env=ENV, check=True, capture_output=True)
    subprocess.run([GO,"build","-o",f"{work}/bin/ahsir","./cmd/ahsir"], cwd=f"{work}/src", env=ENV, check=True)
    subprocess.run([GO,"build","-o",f"{work}/bin/ahsir-agent","./cmd/ahsir-agent"], cwd=f"{work}/src", env=ENV, check=True)

    cfg = f"{work}/ahsir.yaml"
    with open(cfg,"w") as f:
        f.write(f'registry: {{ host: "127.0.0.1", port: {SCHED_PORT}, heartbeat_interval: 10s, heartbeat_timeout: 30s }}\n')
        f.write("port_range: { start: 29951, end: 29960 }\n")
    procs.append(subprocess.Popen([f"{work}/bin/ahsir","start",cfg], env=ENV,
                                  stdout=open(f"{work}/sched.log","w"), stderr=subprocess.STDOUT))
    for _ in range(40):
        if subprocess.run(["curl","-sf","--noproxy","*",f"http://127.0.0.1:{SCHED_PORT}/agents"],
                          env=ENV, capture_output=True).returncode == 0: break
        time.sleep(0.5)
    procs.append(subprocess.Popen([f"{work}/bin/ahsir","ui","--addr",f"127.0.0.1:{UI_PORT}",
                                   "--scheduler",f"http://127.0.0.1:{SCHED_PORT}"], env=ENV,
                                  stdout=open(f"{work}/ui.log","w"), stderr=subprocess.STDOUT))
    time.sleep(2)

    from playwright.sync_api import sync_playwright
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 1500, "height": 1100})
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(f"http://127.0.0.1:{UI_PORT}/", wait_until="networkidle", timeout=25000)
        time.sleep(1.5)
        title = pg.title()
        rendered = bool(title) and pg.locator("body").inner_text().strip() != ""
        pg.screenshot(path=OUT, full_page=False)
        b.close()

    ok = rendered and not errors
    print(json.dumps({"pass": ok, "title": title, "rendered": rendered,
                      "console_errors": errors[:15], "screenshot": OUT}, ensure_ascii=False, indent=1))
    sys.exit(0 if ok else 1)
finally:
    teardown()
