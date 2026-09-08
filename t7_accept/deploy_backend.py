# -*- coding: utf-8 -*-
"""t7 第二轮：后端部署脚本。
步骤：备份 → SFTP 上传 routes.py + auth.py → sha256 校验 → 服务器 py_compile。
重启由面板 MCP 执行（本脚本只打印状态）。
"""
import hashlib
import os
import sys
import time

import paramiko

HOST = "118.24.185.45"
USER = "root"
PASSWORD = "mmfh2025KS686"
REMOTE_BASE = "/www/wwwroot/neo4j-agents"
LOCAL_ROOT = r"D:\python_workspace\neo4j_muti_agents"
VENV_PY = "/www/server/pyporject_evn/neo4j-agents-backend/bin/python"

FILES = [
    ("backend/app/api/routes.py", "backend/app/api/routes.py"),
    ("backend/app/schemas/auth.py", "backend/app/schemas/auth.py"),
]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def run(cli, cmd, timeout=120):
    _, out, err = cli.exec_command(cmd, timeout=timeout)
    return out.read().decode(errors="replace"), err.read().decode(errors="replace")


def main():
    ts = time.strftime("%Y%m%d%H%M%S")
    backup_dir = f"{REMOTE_BASE}/backups/pre-t7-round2-{ts}"
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, banner_timeout=30, auth_timeout=30)

    # 1) 备份
    for _, rel in FILES:
        d = os.path.dirname(f"{backup_dir}/{rel}")
        o, e = run(cli, f"mkdir -p '{d}' && cp -p {REMOTE_BASE}/{rel} '{backup_dir}/{rel}' && echo BACKUP_OK {rel}")
        print(o.strip(), e.strip()[:200])
        if "BACKUP_OK" not in o:
            print("[abort] 备份失败")
            cli.close()
            sys.exit(1)

    # 2) 上传
    sftp = cli.open_sftp()
    for rel_local, rel_remote in FILES:
        lp = os.path.join(LOCAL_ROOT, rel_local)
        rp = f"{REMOTE_BASE}/{rel_remote}"
        sftp.put(lp, rp)
        print(f"[uploaded] {rel_remote} ({os.path.getsize(lp)} B)")
    sftp.close()

    # 3) sha256 校验
    ok = True
    for rel_local, rel_remote in FILES:
        lp = os.path.join(LOCAL_ROOT, rel_local)
        lsha = sha256_file(lp)
        o, _ = run(cli, f"sha256sum {REMOTE_BASE}/{rel_remote}")
        rsha = o.split()[0]
        status = "MATCH" if lsha == rsha else "MISMATCH"
        ok = ok and (lsha == rsha)
        print(f"[verify] {rel_remote}: {status}")

    # 4) 服务器 py_compile
    o, e = run(cli, f"cd {REMOTE_BASE}/backend && {VENV_PY} -m py_compile app/api/routes.py app/schemas/auth.py && echo PYCOMPILE_OK")
    print(o.strip(), e.strip()[:300])
    ok = ok and "PYCOMPILE_OK" in o

    # 5) 记录备份目录
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backup_dir.txt"), "w") as fh:
        fh.write(backup_dir)
    cli.close()
    print("BACKEND_DEPLOY_OK" if ok else "BACKEND_DEPLOY_HAS_ERRORS")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
