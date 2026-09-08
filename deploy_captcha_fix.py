# -*- coding: utf-8 -*-
"""验证码修复部署脚本（临时，勿提交）。
上传改动文件到 118.24.185.45:/www/wwwroot/neo4j-agents/：
  - backend/app/services/captcha_service.py
  - backend/app/api/routes.py
  - frontend/dist/** -> frontend-dist/**
上传前对旧文件/旧目录做 cp 备份（.bak-<ts>）；不动 backend/.env（前后 stat 比对）。
用法: python deploy_captcha_fix.py
"""
import hashlib
import json
import os
import sys
import time

import paramiko

HOST = "118.24.185.45"
PORT = 22
USER = "root"
PASSWORD = "mmfh2025KS686"
REMOTE_BASE = "/www/wwwroot/neo4j-agents"
LOCAL_ROOT = r"D:\python_workspace\neo4j_muti_agents"
MANIFEST_OUT = os.path.join(LOCAL_ROOT, "_deploy_manifest_captcha_fix.json")

BACKEND_FILES = [
    "backend/app/services/captcha_service.py",
    "backend/app/api/routes.py",
]
DIST_DIR = ("frontend", "dist", "frontend-dist")  # (local_parent, local_rel_dir, remote_rel_dir)
ENV_REL = "backend/.env"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def connect():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=PORT, username=USER, password=PASSWORD,
                timeout=30, banner_timeout=30, auth_timeout=30)
    return cli


def run_cmd(cli, cmd, timeout=180):
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


def ensure_remote_dir(sftp, remote_dir):
    parts = [p for p in remote_dir.replace("\\", "/").split("/") if p]
    cur = ""
    for p in parts:
        cur = cur + "/" + p
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)


def collect_tree(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            abs_p = os.path.join(dirpath, fn)
            rel_p = os.path.relpath(abs_p, root).replace("\\", "/")
            out.append((abs_p, rel_p))
    return out


def main():
    ts = time.strftime("%Y%m%d%H%M%S")
    cli = connect()
    print("[ssh] connected, ts=%s" % ts)
    rc, out, _ = run_cmd(cli, "ls -la %s 2>&1 || echo NODIR" % REMOTE_BASE)
    print("[remote base]\n" + out.strip()[:1500])

    # 上传前核对服务器旧文件指纹（诊断期可能打过时钟补丁）
    for rel in BACKEND_FILES:
        remote = "%s/%s" % (REMOTE_BASE, rel)
        rc, out, _ = run_cmd(cli, "md5sum %s 2>&1 || echo MISSING" % remote)
        print("[pre md5] %s -> %s" % (rel, out.strip()[:100]))

    env_before = None
    rc, out, _ = run_cmd(cli, "stat -c '%%s|%%Y|%%n' %s/%s 2>&1 || echo MISSING" % (REMOTE_BASE, ENV_REL))
    env_before = out.strip()
    print("[env before]", env_before)

    # 备份旧文件/旧目录
    for rel in BACKEND_FILES:
        remote = "%s/%s" % (REMOTE_BASE, rel)
        backup = remote + ".bak-" + ts
        rc, out, _ = run_cmd(cli, "test -f %s && cp -a %s %s && echo BACKED_UP || echo NOT_EXISTS" % (remote, remote, backup))
        print("[backup] %s -> %s : %s" % (rel, backup, out.strip().splitlines()[-1]))
    # 清理上一版脚本误建的 REMOTE_BASE/dist 目录（首次 ls 确认部署前不存在）
    rc, out, _ = run_cmd(cli, "rm -rf %s/dist && echo CLEANED || echo CLEAN_FAIL" % REMOTE_BASE)
    print("[cleanup stray dist]", out.strip())

    remote_dist = "%s/%s" % (REMOTE_BASE, DIST_DIR[2])
    backup_dist = remote_dist + ".bak-" + ts
    rc, out, _ = run_cmd(cli, "test -d %s && cp -a %s %s && echo BACKED_UP || echo NOT_EXISTS" % (remote_dist, remote_dist, backup_dist))
    print("[backup] %s -> %s : %s" % (DIST_DIR[2], backup_dist, out.strip().splitlines()[-1]))

    sftp = cli.open_sftp()
    manifest = {"ts": ts, "backend": {}, "dist": {}}
    for rel in BACKEND_FILES:
        local = os.path.join(LOCAL_ROOT, rel)
        remote = "%s/%s" % (REMOTE_BASE, rel)
        ensure_remote_dir(sftp, os.path.dirname(remote))
        sftp.put(local, remote)
        manifest["backend"][rel] = {"size": os.path.getsize(local), "sha256": sha256_file(local)}
        print("[put] %s (%d bytes)" % (rel, os.path.getsize(local)))

    local_dist = os.path.join(LOCAL_ROOT, DIST_DIR[0], DIST_DIR[1])
    n = 0
    for abs_p, rel_p in collect_tree(local_dist):
        remote = "%s/%s/%s" % (REMOTE_BASE, DIST_DIR[2], rel_p)
        ensure_remote_dir(sftp, os.path.dirname(remote))
        sftp.put(abs_p, remote)
        manifest["dist"][rel_p] = {"size": os.path.getsize(abs_p), "sha256": sha256_file(abs_p)}
        n += 1
    print("[put] dist files=%d" % n)
    sftp.close()

    # 校验 .env 未被触碰
    rc, out, _ = run_cmd(cli, "stat -c '%%s|%%Y|%%n' %s/%s 2>&1 || echo MISSING" % (REMOTE_BASE, ENV_REL))
    env_after = out.strip()
    print("[env after ]", env_after)
    if env_before != env_after:
        print("[FATAL] backend/.env changed during upload!")
        sys.exit(3)
    print("[env] untouched - OK")

    # 远程 sha256 校验 backend 两文件
    for rel in BACKEND_FILES:
        remote = "%s/%s" % (REMOTE_BASE, rel)
        rc, out, _ = run_cmd(cli, "sha256sum %s 2>&1" % remote)
        remote_sha = out.strip().split()[0] if rc == 0 else "ERR:" + out.strip()
        local_sha = manifest["backend"][rel]["sha256"]
        print("[sha256 %s] %s local=%s remote=%s" % (
            "MATCH" if remote_sha == local_sha else "MISMATCH", rel, local_sha[:12], remote_sha[:12]))

    with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    cli.close()
    print("[done] manifest=%s" % MANIFEST_OUT)


if __name__ == "__main__":
    main()
