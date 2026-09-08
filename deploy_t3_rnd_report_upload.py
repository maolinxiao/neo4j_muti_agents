# -*- coding: utf-8 -*-
"""T3(研发协同主控汇总报告化+面板重构) 上线脚本：上传 backend 2 文件 + frontend dist 4 文件并做 sha256 核验。
用法: python deploy_t3_rnd_report_upload.py
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
    ("backend/app/db/seed_data.py", "backend/app/db/seed_data.py"),
    ("backend/app/services/rnd_workflow_orchestrator.py", "backend/app/services/rnd_workflow_orchestrator.py"),
    ("frontend/dist/index.html", "frontend-dist/index.html"),
    ("frontend/dist/assets/index-DXeoezzh.js", "frontend-dist/assets/index-DXeoezzh.js"),
    ("frontend/dist/assets/index-5F4MD3IX.css", "frontend-dist/assets/index-5F4MD3IX.css"),
    ("frontend/dist/assets/HeroKnowledgeScene-BOEHd5n6.js", "frontend-dist/assets/HeroKnowledgeScene-BOEHd5n6.js"),
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
    ok = True
    for rel_local, rel_remote in FILES:
        lp = os.path.join(LOCAL_ROOT, rel_local)
        rp = REMOTE_BASE + "/" + rel_remote
        if not os.path.exists(lp):
            print(f"[ERROR] local missing: {lp}")
            ok = False
            continue
        sftp.put(lp, rp)
        size = os.path.getsize(lp)
        print(f"[uploaded] {rel_remote} ({size} B)")
    sftp.close()
    # 用 ssh 真实校验
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
