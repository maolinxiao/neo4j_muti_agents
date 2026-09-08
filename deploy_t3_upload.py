# -*- coding: utf-8 -*-
"""T3 上传脚本（临时，勿提交）：
上传 backend/app、requirements.txt、run_server.py、根 scripts 3 文件、图谱数据、frontend/dist 到
118.24.185.45:/www/wwwroot/neo4j-agents/。严禁覆盖 backend/.env。
用法: python deploy_t3_upload.py --phase app,scripts,data,dist [--verify-sha]
"""
import argparse
import hashlib
import json
import os
import sys

import paramiko

HOST = "118.24.185.45"
PORT = 22
USER = "root"
PASSWORD = "mmfh2025KS686"
REMOTE_BASE = "/www/wwwroot/neo4j-agents"
LOCAL_ROOT = r"D:\python_workspace\neo4j_muti_agents"
DATA_ROOT = r"D:\工作\多智能体-宋\最新数据\6-4\药食同源agent项目"
MANIFEST_OUT = os.path.join(LOCAL_ROOT, "_deploy_manifest_t3.json")
ENV_REL = "backend/.env"

GROUPS = {
    "app": [{"local": os.path.join(LOCAL_ROOT, "backend", "app"), "remote": "backend/app", "exclude": {"__pycache__"}}],
    "scripts": [
        {"local": os.path.join(LOCAL_ROOT, "requirements.txt"), "remote": "backend/requirements.txt"},
        {"local": os.path.join(LOCAL_ROOT, "backend", "scripts", "run_server.py"), "remote": "backend/scripts/run_server.py"},
        {"local": os.path.join(LOCAL_ROOT, "scripts", "import_agent_kg_0604.py"), "remote": "scripts/import_agent_kg_0604.py"},
        {"local": os.path.join(LOCAL_ROOT, "scripts", "restore_neo4j_backup.py"), "remote": "scripts/restore_neo4j_backup.py"},
        {"local": os.path.join(LOCAL_ROOT, "scripts", "validate_qa_routing.py"), "remote": "scripts/validate_qa_routing.py"},
    ],
    "data": [{"local": DATA_ROOT, "remote": "data", "exclude": set()}],
    "dist": [{"local": os.path.join(LOCAL_ROOT, "frontend", "dist"), "remote": "frontend-dist", "exclude": set()}],
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def collect_local_tree(root, exclude_dirs):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fn in filenames:
            abs_p = os.path.join(dirpath, fn)
            rel_p = os.path.relpath(abs_p, root).replace("\\", "/")
            out.append((abs_p, rel_p))
    return out


def connect():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=PORT, username=USER, password=PASSWORD,
                timeout=30, banner_timeout=30, auth_timeout=30)
    return cli


def run_cmd(cli, cmd, timeout=120):
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


def remote_stat_env(cli):
    rc, out, _ = run_cmd(cli, "stat -c '%s|%Y|%n' " + REMOTE_BASE + "/" + ENV_REL + " 2>&1 || echo MISSING")
    return out.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="app,scripts,data")
    ap.add_argument("--verify-sha", action="store_true")
    args = ap.parse_args()
    phases = [p.strip() for p in args.phase.split(",") if p.strip()]

    cli = connect()
    print("[ssh] connected")
    rc, out, err = run_cmd(cli, "ls -la %s 2>&1 || echo NODIR" % REMOTE_BASE)
    print("[remote base]\n" + out.strip()[:2000])
    env_before = remote_stat_env(cli)
    print("[env before]", env_before)

    manifest = {}
    if os.path.exists(MANIFEST_OUT):
        with open(MANIFEST_OUT, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    sftp = cli.open_sftp()
    total_uploaded = 0
    for phase in phases:
        items = GROUPS[phase]
        group_stat = {"files": 0, "bytes": 0}
        if phase not in manifest:
            manifest[phase] = {}
        for it in items:
            local = it["local"]
            remote_rel = it["remote"]
            if not os.path.exists(local):
                print("[ERROR] local missing: %s" % local)
                sys.exit(2)
            if os.path.isfile(local):
                files = [(local, "")]
            else:
                files = collect_local_tree(local, it.get("exclude", set()))
            for abs_p, rel_p in files:
                remote_abs = REMOTE_BASE + "/" + remote_rel + ("/" + rel_p if rel_p else "")
                remote_abs = remote_abs.replace("\\", "/")
                ensure_remote_dir(sftp, os.path.dirname(remote_abs))
                size = os.path.getsize(abs_p)
                sftp.put(abs_p, remote_abs)
                key = remote_rel + ("/" + rel_p if rel_p else "")
                manifest[phase][key] = {"size": size, "sha256": sha256_file(abs_p)}
                group_stat["files"] += 1
                group_stat["bytes"] += size
                total_uploaded += 1
        print("[%s] uploaded files=%d bytes=%d" % (phase, group_stat["files"], group_stat["bytes"]))

    env_after = remote_stat_env(cli)
    print("[env after ]", env_after)
    if env_before != env_after:
        print("[FATAL] backend/.env changed during upload!")
        sys.exit(3)
    print("[env] untouched - OK")

    with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    rc, out, _ = run_cmd(cli, "find %s -type f | wc -l" % REMOTE_BASE)
    print("[remote total files]", out.strip())

    if args.verify_sha:
        import random
        data_files = [k for k in manifest.get("data", {})]
        sample = sorted(random.sample(data_files, min(3, len(data_files))))
        for k in sample:
            local_sha = manifest["data"][k]["sha256"]
            rc, out, _ = run_cmd(cli, "sha256sum '%s/%s' 2>&1" % (REMOTE_BASE, k))
            remote_sha = out.strip().split()[0] if rc == 0 else "ERR:" + out.strip()
            match = "MATCH" if remote_sha == local_sha else "MISMATCH"
            print("[sha256 %s] %s local=%s remote=%s" % (match, k, local_sha[:12], remote_sha[:12]))

    sftp.close()
    cli.close()
    print("[done] total_uploaded=%d manifest=%s" % (total_uploaded, MANIFEST_OUT))


if __name__ == "__main__":
    main()
