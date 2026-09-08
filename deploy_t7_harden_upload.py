# -*- coding: utf-8 -*-
"""T7 加固上线脚本：上传 rnd_workflow_orchestrator.py 并 sha256 核验。用法: python deploy_t7_harden_upload.py
"""
import hashlib
import os
import paramiko

HOST = "118.24.185.45"
PORT = 22
USER = "root"
PASSWORD = "mmfh2025KS686"
LOCAL_ROOT = r"D:\python_workspace\neo4j_muti_agents"
REMOTE_BASE = "/www/wwwroot/neo4j-agents"

FILES = [
    ("backend/app/services/rnd_workflow_orchestrator.py", "backend/app/services/rnd_workflow_orchestrator.py"),
]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30, banner_timeout=30, auth_timeout=30)
    sftp = cli.open_sftp()
    for rel_local, rel_remote in FILES:
        lp = os.path.join(LOCAL_ROOT, rel_local)
        rp = REMOTE_BASE + "/" + rel_remote
        sftp.put(lp, rp)
        print(f"[uploaded] {rel_remote} ({os.path.getsize(lp)} B)")
    sftp.close()
    ok = True
    for rel_local, rel_remote in FILES:
        lp = os.path.join(LOCAL_ROOT, rel_local)
        rp = REMOTE_BASE + "/" + rel_remote
        lsha = sha256_file(lp)
        _, out, _ = cli.exec_command(f"sha256sum {rp}", timeout=60)
        rsha = out.read().decode().split()[0]
        status = "MATCH" if lsha == rsha else "MISMATCH"
        if lsha != rsha:
            ok = False
        print(f"[verify] {rel_remote}: {status}")
    cli.close()
    print("ALL_OK" if ok else "HAS_ERRORS")


if __name__ == "__main__":
    main()
