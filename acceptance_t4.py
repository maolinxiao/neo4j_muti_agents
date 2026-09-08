# -*- coding: utf-8 -*-
"""T4 线上验收脚本（临时，勿提交）。

原则：
- 管理员密码仅从服务器 backend/.env 读取进内存（paramiko），绝不出现在任何输出/日志。
- access_token 仅写入本地权限受限文件（--token-out），输出一律脱敏。
- 验证码文本由调用方（agent 读图）提供：先 'captcha' 出图，再携带 captcha_id/text 调后续命令。

用法示例：
  python acceptance_t4.py health
  python acceptance_t4.py captcha --out captcha_input/c1.png
  python acceptance_t4.py login --admin-env --captcha-id X --captcha-text AB12 --token-out tokens/admin.tok
  python acceptance_t4.py register --captcha-id X --captcha-text AB12 --username ua --password Pw123456
  python acceptance_t4.py enable --token-file tokens/admin.tok --user-id <id>
  python acceptance_t4.py list-users --token-file tokens/admin.tok
  python acceptance_t4.py create-session --token-file tokens/a.tok
  python acceptance_t4.py list-sessions --token-file tokens/b.tok
  python acceptance_t4.py delete-user --token-file tokens/admin.tok --user-id <id>
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

import paramiko

BASE = "http://118.24.185.45"
LOCAL_ROOT = r"D:\python_workspace\neo4j_muti_agents"
SSH = dict(hostname="118.24.185.45", port=22, username="root", password="mmfh2025KS686")


def http(method, path, data=None, token=None, timeout=60):
    url = BASE + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(raw) if raw else None), None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = raw
        return exc.code, body, None
    except Exception as exc:  # noqa: BLE001
        return 0, None, str(exc)


def read_server_env():
    """从服务器读取 .env 全文（仅内存），返回 dict。绝不打印内容。"""
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(**SSH, timeout=30, banner_timeout=30, auth_timeout=30)
    _, stdout, stderr = cli.exec_command("cat /www/wwwroot/neo4j-agents/backend/.env", timeout=60)
    text = stdout.read().decode("utf-8", "replace")
    cli.close()
    env = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def load_token(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def save_token(path, token):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(token)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def mask(s):
    if not s:
        return ""
    return s[:6] + "..." + s[-4:] if len(s) > 12 else "***"


def json_out(label, status, data, err=None, extra=None):
    rec = {"label": label, "status": status, "ok": status == 200,
           "data": data, "error": err}
    if extra:
        rec.update(extra)
    print(json.dumps(rec, ensure_ascii=False, default=str))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("health")
    p = sub.add_parser("captcha")
    p.add_argument("--out", required=True)

    p = sub.add_parser("captcha-auto")
    p.add_argument("--out", required=True)
    p.add_argument("--font", default=os.path.join(LOCAL_ROOT, "captcha_input", "DejaVuSans.ttf"))

    p = sub.add_parser("register")
    p.add_argument("--captcha-id", required=True)
    p.add_argument("--captcha-text", required=True)
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--email", default=None)

    p = sub.add_parser("login")
    p.add_argument("--captcha-id", required=True)
    p.add_argument("--captcha-text", required=True)
    p.add_argument("--username", default=None)
    p.add_argument("--password", default=None)
    p.add_argument("--admin-env", action="store_true", help="从服务器 .env 读取管理员账号密码")
    p.add_argument("--token-out", required=True)

    p = sub.add_parser("me")
    p.add_argument("--token-file", required=True)

    p = sub.add_parser("enable")
    p.add_argument("--token-file", required=True)
    p.add_argument("--user-id", required=True)

    p = sub.add_parser("create-user")
    p.add_argument("--token-file", required=True)
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--email", default=None)
    p.add_argument("--role", default="user")

    p = sub.add_parser("list-users")
    p.add_argument("--token-file", required=True)
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--page-size", type=int, default=50)

    p = sub.add_parser("create-session")
    p.add_argument("--token-file", required=True)

    p = sub.add_parser("list-sessions")
    p.add_argument("--token-file", required=True)

    p = sub.add_parser("delete-user")
    p.add_argument("--token-file", required=True)
    p.add_argument("--user-id", required=True)

    args = ap.parse_args()

    if args.cmd == "health":
        st, data, err = http("GET", "/api/health")
        json_out("health", st, data, err)
        sys.exit(0 if st == 200 else 1)

    if args.cmd == "captcha":
        st, data, err = http("GET", "/api/auth/captcha")
        if st != 200:
            json_out("captcha", st, data, err)
            sys.exit(1)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(base64.b64decode(data["image_base64"]))
        body = {"label": "captcha", "status": st, "ok": True,
                "captcha_id": data["captcha_id"], "image_saved": os.path.abspath(args.out),
                "mime": data.get("mime")}
        print(json.dumps(body, ensure_ascii=False))
        sys.exit(0)

    if args.cmd == "captcha-auto":
        st, data, err = http("GET", "/api/auth/captcha")
        if st != 200:
            json_out("captcha-auto", st, data, err)
            sys.exit(1)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "wb") as f:
            f.write(base64.b64decode(data["image_base64"]))
        import solve2 as sc
        res = sc.solve(os.path.abspath(args.out), args.font)
        text = "".join(c for c, _ in res)
        print(json.dumps({
            "label": "captcha-auto", "status": st, "ok": True,
            "captcha_id": data["captcha_id"], "solved_text": text,
            "per_char": res, "image_saved": os.path.abspath(args.out),
        }, ensure_ascii=False))
        sys.exit(0)

    if args.cmd == "register":
        payload = {"username": args.username, "password": args.password,
                   "captcha_id": args.captcha_id, "captcha_text": args.captcha_text}
        if args.email:
            payload["email"] = args.email
        st, data, err = http("POST", "/api/auth/register", payload)
        json_out("register", st, data, err)
        sys.exit(0 if st == 200 else 1)

    if args.cmd == "login":
        if args.admin_env:
            env = read_server_env()
            username = env.get("DEFAULT_ADMIN_USERNAME") or "admin"
            password = env.get("DEFAULT_ADMIN_PASSWORD")
            if not password:
                json_out("login-admin", 0, None, "服务器 .env 中未找到 DEFAULT_ADMIN_PASSWORD")
                sys.exit(1)
            print(json.dumps({"label": "login-admin", "env_user": username, "pw_read": True}, ensure_ascii=False))
        else:
            username, password = args.username, args.password
        payload = {"username": username, "password": password,
                   "captcha_id": args.captcha_id, "captcha_text": args.captcha_text}
        st, data, err = http("POST", "/api/auth/login", payload)
        if st == 200:
            save_token(args.token_out, data["access_token"])
            json_out("login", st, {"token_masked": mask(data["access_token"]),
                                   "expires_at": data.get("expires_at"),
                                   "user": data.get("user")}, err,
                     extra={"token_saved": os.path.abspath(args.token_out)})
        else:
            json_out("login", st, data, err)
        sys.exit(0 if st == 200 else 1)

    if args.cmd == "me":
        tok = load_token(args.token_file)
        st, data, err = http("GET", "/api/auth/me", token=tok)
        json_out("me", st, data, err)
        sys.exit(0 if st == 200 else 1)

    if args.cmd == "enable":
        tok = load_token(args.token_file)
        st, data, err = http("PUT", "/api/admin/users/%s" % args.user_id, {"is_active": True}, token=tok)
        json_out("enable", st, data, err)
        sys.exit(0 if st == 200 else 1)

    if args.cmd == "create-user":
        tok = load_token(args.token_file)
        payload = {"username": args.username, "password": args.password, "role": args.role}
        if args.email:
            payload["email"] = args.email
        st, data, err = http("POST", "/api/admin/users", payload, token=tok)
        if st == 200 and isinstance(data, dict) and "generated_password" not in data:
            data = {k: v for k, v in data.items() if k != "password_hash"}
        json_out("create-user", st, data, err)
        sys.exit(0 if st == 200 else 1)

    if args.cmd == "list-users":
        tok = load_token(args.token_file)
        st, data, err = http("GET", "/api/admin/users?page=%d&page_size=%d" % (args.page, args.page_size), token=tok)
        if st == 200 and isinstance(data, dict):
            items = data.get("items", [])
            summary = [{"id": u.get("id"), "username": u.get("username"), "role": u.get("role"),
                        "is_active": u.get("is_active")} for u in items]
            json_out("list-users", st, {"total": data.get("total"), "page": data.get("page"),
                                        "items": summary}, err)
        else:
            json_out("list-users", st, data, err)
        sys.exit(0 if st == 200 else 1)

    if args.cmd == "create-session":
        tok = load_token(args.token_file)
        st, data, err = http("POST", "/api/chat/sessions", {}, token=tok)
        json_out("create-session", st, data, err)
        sys.exit(0 if st == 200 else 1)

    if args.cmd == "list-sessions":
        tok = load_token(args.token_file)
        st, data, err = http("GET", "/api/chat/sessions", token=tok)
        json_out("list-sessions", st, data, err)
        sys.exit(0 if st == 200 else 1)

    if args.cmd == "delete-user":
        tok = load_token(args.token_file)
        st, data, err = http("DELETE", "/api/admin/users/%s" % args.user_id, token=tok)
        json_out("delete-user", st, data, err)
        sys.exit(0 if st == 200 else 1)

    print("[ERROR] unknown cmd", args.cmd)
    sys.exit(2)


if __name__ == "__main__":
    main()
