# -*- coding: utf-8 -*-
"""t3 公网回归（临时脚本，勿提交）。
步骤：
1) GET / (200) 且 index.html 引用新 bundle hash
2) 新资源逐个 200（assets/*.js|css + 根资源）
3) /login 200
4) /api/health 200（postgres/neo4j/llm 均 true）
5) 登录冒烟：captcha(OCR) -> login(admin-env) -> me -> logout
用法: python regress_t3_public.py
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

BASE = "http://118.24.185.45"
ROOT = r"D:\python_workspace\neo4j_muti_agents"
DIST = os.path.join(ROOT, "frontend", "dist")
TOK = os.path.join(ROOT, "tokens", "admin_t3.tok")
FONT = os.path.join(ROOT, "captcha_input", "DejaVuSans.ttf")

RESULTS = []


def check(item, ok, detail=""):
    RESULTS.append((item, bool(ok), detail))
    print("[RESULT] %s | %s | %s" % ("PASS" if ok else "FAIL", item, detail))


def http_get(path, timeout=60):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def run(args):
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True, cwd=ROOT, timeout=180)
    return p.returncode, p.stdout.strip()


def main():
    # 1) 首页
    st, html = http_get("/")
    check("GET / 200", st == 200, "status=%d" % st)
    refs = sorted(set(re.findall(r'(?:src|href)="([^"]+)"', html)))
    check("index.html has new main bundle", any("index-CDUurgba.js" in r for r in refs), "refs=%s" % refs)

    # 2) 新资源 200
    new_files = []
    for dirpath, dirnames, filenames in os.walk(DIST):
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), DIST).replace("\\", "/")
            new_files.append(rel)
    all_ok = True
    details = []
    for rel in sorted(new_files):
        st, _ = http_get("/" + rel)
        details.append("%s=%d" % (rel, st))
        if st != 200:
            all_ok = False
    check("all new dist resources 200", all_ok, "; ".join(details)[:600])

    # 3) /login
    st, _ = http_get("/login")
    check("GET /login 200", st == 200, "status=%d" % st)

    # 4) health
    st, body = http_get("/api/health")
    ok_h = False
    detail = ""
    if st == 200:
        try:
            d = json.loads(body)
            ok_h = all(d.get(k) for k in ("postgres", "neo4j")) and (d.get("llm") or d.get("llm_configured"))
            detail = json.dumps(d.get("summary") or d, ensure_ascii=False)[:300]
        except Exception:  # noqa: BLE001
            detail = body[:200]
    check("health 200 (postgres/neo4j/llm)", st == 200 and ok_h, "status=%d %s" % (st, detail))

    # 5) 登录冒烟
    rc, out = run(["acceptance_t4.py", "captcha-auto", "--out", os.path.join(ROOT, "captcha_input", "t3_cap.png"), "--font", FONT])
    check("captcha-auto OCR", rc == 0, out[:200] if rc else "rc=%d" % rc)
    info = json.loads(out.splitlines()[-1]) if out else {}
    cid, ctext = info.get("captcha_id", ""), info.get("solved_text", "")
    rc, out = run(["acceptance_t4.py", "login", "--admin-env", "--captcha-id", cid, "--captcha-text", ctext, "--token-out", TOK])
    check("login (admin-env) 200", rc == 0, out[:240] if rc else "rc=%d" % rc)
    token = ""
    if os.path.exists(TOK):
        with open(TOK, "r", encoding="utf-8") as f:
            token = f.read().strip()
    rc, out = run(["acceptance_t4.py", "me", "--token-file", TOK])
    check("me 200", rc == 0, out[:200] if rc else "rc=%d" % rc)
    if token:
        req = urllib.request.Request(BASE + "/api/auth/logout", data=b"{}", method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                logout_st = r.status
        except urllib.error.HTTPError as e:
            logout_st = e.code
        check("logout 200", logout_st == 200, "status=%d" % logout_st)
    else:
        check("logout 200", False, "no token available")

    n_ok = sum(1 for _, ok, _ in RESULTS if ok)
    print("\n[SUMMARY] %d/%d PASS" % (n_ok, len(RESULTS)))
    with open(os.path.join(ROOT, ".tmp-showcase-t3", "regress_public.json"), "w", encoding="utf-8") as f:
        json.dump([{"item": i, "ok": o, "detail": d} for i, o, d in RESULTS], f, ensure_ascii=False, indent=1)
    sys.exit(0 if n_ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
