# -*- coding: utf-8 -*-
"""验证码修复自验脚本（临时，勿提交）。
公网验证：两次取码 id 不同、错误文本语义、重试不被一次性误伤、attempts 上限、
求解器取正确文本 → 小写提交（大小写不敏感）→ 登录成功 → 复用同 id 得 used 语义。
用法: python verify_captcha_fix.py
"""
import base64
import json
import subprocess
import sys
import time

import paramiko
import requests

BASE = "http://118.24.185.45"
HOST = "118.24.185.45"
SSH_PASSWORD = "mmfh2025KS686"
SOLVE2 = r"D:\python_workspace\neo4j_muti_agents\solve2.py"
PNG_OUT = r"D:\python_workspace\neo4j_muti_agents\captcha_input\verify_shot.png"


def get_captcha():
    r = requests.get(BASE + "/api/auth/captcha", timeout=30)
    return r.status_code, r.json()


def login(username, password, captcha_id, captcha_text):
    r = requests.post(
        BASE + "/api/auth/login",
        json={"username": username, "password": password, "captcha_id": captcha_id, "captcha_text": captcha_text},
        timeout=30,
    )
    try:
        body = r.json()
    except Exception:
        body = r.text[:200]
    return r.status_code, body


def fetch_admin_password():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username="root", password=SSH_PASSWORD,
                timeout=30, banner_timeout=30, auth_timeout=30)
    _, out, _ = cli.exec_command(
        "grep -E '^DEFAULT_ADMIN_PASSWORD=' /www/wwwroot/neo4j-agents/backend/.env | head -1 | cut -d= -f2-", timeout=30)
    pwd = out.read().decode("utf-8", "replace").strip()
    cli.close()
    return pwd


def solve(png_path):
    proc = subprocess.run([sys.executable, SOLVE2, png_path], capture_output=True, text=True, timeout=180)
    text = ""
    for line in proc.stdout.splitlines():
        if line.startswith("[text]"):
            text = line.split("]", 1)[1].strip()
    return text, proc.stdout


def logout(token):
    r = requests.post(BASE + "/api/auth/logout", headers={"Authorization": "Bearer " + token}, timeout=30)
    return r.status_code


def main():
    results = []

    # 1) 两次取码 id 不同
    s1, j1 = get_captcha()
    s2, j2 = get_captcha()
    ids_differ = j1.get("captcha_id") != j2.get("captcha_id")
    results.append(("two_get_ids_differ", s1 == 200 and s2 == 200 and ids_differ,
                    "s1=%s s2=%s differ=%s id1=%s.." % (s1, s2, ids_differ, str(j1.get("captcha_id"))[:12])))
    cid = j2["captcha_id"]

    # 2) 新 id + 错误文本 → 应是"文本错误"，而非"id 失效"
    st, body = login("admin", "dummy", cid, "zzzz")
    detail = body.get("detail", "") if isinstance(body, dict) else str(body)
    results.append(("fresh_id_wrong_text_is_text_mismatch", st == 400 and "输入错误" in detail,
                    "st=%s detail=%s" % (st, detail)))

    # 3) 同 id 第二次错误提交 → 仍可重试（不被一次性误伤）
    st2, body2 = login("admin", "dummy", cid, "yyyy")
    detail2 = body2.get("detail", "") if isinstance(body2, dict) else str(body2)
    results.append(("same_id_retry_not_burned", st2 == 400 and "输入错误" in detail2,
                    "st=%s detail=%s" % (st2, detail2)))

    # 4) 连续错到 attempts 上限（captcha_fail_max=5，第 5 次错达到上限）
    last = None
    for k in range(3, 6):
        stk, bodyk = login("admin", "dummy", cid, "kk%02d" % k)
        last = (stk, bodyk)
    detail5 = last[1].get("detail", "") if isinstance(last[1], dict) else str(last[1])
    results.append(("attempts_cap_on_5th", last[0] == 400 and "次数过多" in detail5,
                    "st=%s detail=%s" % (last[0], detail5)))
    st6, body6 = login("admin", "dummy", cid, "xxxx")
    detail6 = body6.get("detail", "") if isinstance(body6, dict) else str(body6)
    results.append(("attempts_cap_still_reported", st6 == 400 and "次数过多" in detail6,
                    "st=%s detail=%s" % (st6, detail6)))

    # 5) 求解器链路：取码 → 求解 → 小写提交（大小写不敏感）→ 期望登录成功
    admin_pwd = fetch_admin_password()
    login_ok = False
    used_ok = False
    solved_text = ""
    for attempt in range(1, 4):
        s, j = get_captcha()
        cid2 = j["captcha_id"]
        with open(PNG_OUT, "wb") as f:
            f.write(base64.b64decode(j["image_base64"]))
        solved_text, solver_out = solve(PNG_OUT)
        print("[solve attempt %d] text=%s" % (attempt, solved_text))
        if len(solved_text) != 4:
            continue
        st, body = login("admin", admin_pwd, cid2, solved_text.lower())
        if st == 200:
            login_ok = True
            token = body.get("access_token", "")
            logout(token)
            # 6) 复用同 id + 正确文本 → used 语义
            st_u, body_u = login("admin", admin_pwd, cid2, solved_text.lower())
            detail_u = body_u.get("detail", "") if isinstance(body_u, dict) else str(body_u)
            used_ok = st_u == 400 and "已被使用" in detail_u
            results.append(("used_semantics_after_success", used_ok, "st=%s detail=%s" % (st_u, detail_u)))
            break
        else:
            detail = body.get("detail", "") if isinstance(body, dict) else str(body)
            print("[solve attempt %d] login st=%s detail=%s" % (attempt, st, detail))
    results.append(("solver_case_insensitive_login_200", login_ok,
                    "solved_text_len=%d" % len(solved_text)))

    print("\n===== RESULTS =====")
    all_pass = True
    for name, ok, evidence in results:
        print("[%s] %s  %s" % ("PASS" if ok else "FAIL", name, evidence))
        all_pass = all_pass and ok
    print("ALL_PASS=%s" % all_pass)
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
