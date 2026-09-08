# -*- coding: utf-8 -*-
"""t7: 服务器现状盘点（只读）。"""
import paramiko

HOST = "118.24.185.45"
USER = "root"
PASSWORD = "mmfh2025KS686"
REMOTE_BASE = "/www/wwwroot/neo4j-agents"


def run(cli, cmd):
    _, out, err = cli.exec_command(cmd, timeout=120)
    o = out.read().decode(errors="replace")
    e = err.read().decode(errors="replace")
    return o, e


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, banner_timeout=30, auth_timeout=30)
    cmds = [
        ("backend files", f"ls -la {REMOTE_BASE}/backend/app/api/routes.py {REMOTE_BASE}/backend/app/schemas/auth.py {REMOTE_BASE}/backend/scripts/run_server.py 2>&1"),
        ("backend sha256", f"sha256sum {REMOTE_BASE}/backend/app/api/routes.py {REMOTE_BASE}/backend/app/schemas/auth.py 2>&1"),
        ("frontend-dist ls", f"ls -la {REMOTE_BASE}/frontend-dist/ {REMOTE_BASE}/frontend-dist/assets/ 2>&1"),
        ("frontend index.html", f"cat {REMOTE_BASE}/frontend-dist/index.html 2>&1"),
        ("health", "curl -s -m 10 http://127.0.0.1:8000/api/health"),
        ("public index", "curl -s -m 10 -H 'Host: 118.24.185.45' http://127.0.0.1/ | head -c 800"),
        ("nginx conf path", "ls /www/server/panel/vhost/nginx/ 2>&1 | head"),
        ("backups dir", f"ls {REMOTE_BASE}/backups/ 2>&1 | tail -15"),
        ("env stat", f"stat -c '%a %U %s %y' {REMOTE_BASE}/backend/.env 2>&1"),
        ("python venv pillow", "/www/server/pyporject_evn/neo4j-agents-backend/bin/pip list 2>/dev/null | grep -iE 'pillow|multipart|psycopg|fastapi'"),
    ]
    for name, cmd in cmds:
        o, e = run(cli, cmd)
        print(f"===== {name} =====")
        print(o.strip())
        if e.strip():
            print("[stderr]", e.strip()[:300])
    cli.close()


if __name__ == "__main__":
    main()
