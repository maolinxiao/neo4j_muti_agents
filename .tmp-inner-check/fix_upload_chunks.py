# -*- coding: utf-8 -*-
"""修复 T2 清理误删：补传动态 chunk（HeroKnowledgeScene-*.js/css）并校验 sha256。"""
import hashlib
import os
import sys

import paramiko

HOST = "118.24.185.45"
PASSWORD = "mmfh2025KS686"
REMOTE_DIR = "/www/wwwroot/neo4j-agents/frontend-dist/assets"
LOCAL_DIR = r"D:\python_workspace\neo4j_muti_agents\frontend\dist\assets"
FILES = ["HeroKnowledgeScene-x0ezEfm_.js", "HeroKnowledgeScene-DVgML9Jm.css"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username="root", password=PASSWORD, timeout=30)
    sftp = cli.open_sftp()
    for fn in FILES:
        local = os.path.join(LOCAL_DIR, fn)
        remote = REMOTE_DIR + "/" + fn
        if not os.path.exists(local):
            print("[ERROR] local missing", local)
            sys.exit(2)
        sftp.put(local, remote)
        local_sha = sha256_file(local)
        _, stdout, _ = cli.exec_command("sha256sum '%s'" % remote, timeout=30)
        remote_sha = stdout.read().decode().strip().split()[0]
        ok = remote_sha == local_sha
        print(f"{fn}: uploaded sha={'MATCH' if ok else 'MISMATCH'} local={local_sha[:12]} remote={remote_sha[:12]}")
    sftp.close()
    _, stdout, _ = cli.exec_command(
        "chmod 644 %s/%s %s/%s && ls -l %s/ | tail -8"
        % (REMOTE_DIR, FILES[0], REMOTE_DIR, FILES[1], REMOTE_DIR), timeout=30)
    print(stdout.read().decode())
    cli.close()
    print("FIX DONE")


if __name__ == "__main__":
    main()
