# -*- coding: utf-8 -*-
"""T4 上线脚本（临时，勿提交）：
1) 上线前备份：pg_dump neo4j_agents -> backups/pg/pre-multiuser-<ts>.sql.gz；cp backend/.env -> backups/env/pre-multiuser.env
2) 上传 backend/app（排除 __pycache__）、backend/requirements.txt、backend/scripts/run_server.py、
   backend/.env.example、frontend/dist -> /www/wwwroot/neo4j-agents/。
重要：绝不覆盖 backend/.env（上传前后 stat 对比，变化即 FATAL）。
用法: python deploy_t4_upload.py [--verify-sha]
"""
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
MANIFEST_OUT = os.path.join(LOCAL_ROOT, "_deploy_manifest_t4.json")
ENV_REL = "backend/.env"

GROUPS = {
    "app": [{"local": os.path.join(LOCAL_ROOT, "backend", "app"), "remote": "backend/app",
             "exclude": {"__pycache__", ".pytest_cache"}}],
    "scripts": [
        {"local": os.path.join(LOCAL_ROOT, "requirements.txt"), "remote": "backend/requirements.txt"},
        {"local": os.path.join(LOCAL_ROOT, "backend", "scripts", "run_server.py"), "remote": "backend/scripts/run_server.py"},
        {"local": os.path.join(LOCAL_ROOT, "backend", ".env.example"), "remote": "backend/.env.example"},
    ],
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


def run_cmd(cli, cmd, timeout=600):
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


def do_backup(cli):
    ts = None
    rc, out, err = run_cmd(cli, "date +%F%H%M")
    ts = out.strip()
    print("[backup] timestamp =", ts)
    # 目录
    rc, out, err = run_cmd(cli, "mkdir -p %s/backups/pg %s/backups/env && echo OK" % (REMOTE_BASE, REMOTE_BASE))
    print("[backup] mkdir:", out.strip(), err.strip()[:200])
    pg_cmd = (
        "sudo -u postgres pg_dump -d neo4j_agents | gzip > %s/backups/pg/pre-multiuser-%s.sql.gz; "
        "echo RC=$?" % (REMOTE_BASE, ts)
    )
    rc, out, err = run_cmd(cli, pg_cmd, timeout=900)
    print("[backup] pg_dump rc:", out.strip(), err.strip()[:300])
    rc, out, err = run_cmd(cli, "ls -l %s/backups/pg/pre-multiuser-%s.sql.gz; gzip -t %s/backups/pg/pre-multiuser-%s.sql.gz && echo GZIP_OK"
                           % (REMOTE_BASE, ts, REMOTE_BASE, ts))
    print("[backup] pg result:", out.strip(), err.strip()[:300])
    rc, out, err = run_cmd(cli, "cp -p %s/%s %s/backups/env/pre-multiuser.env && echo CP_OK && stat -c '%%a|%%U:%%G|%%s|%%n' %s/backups/env/pre-multiuser.env"
                           % (REMOTE_BASE, ENV_REL, REMOTE_BASE, REMOTE_BASE))
    print("[backup] env copy:", out.strip(), err.strip()[:300])
    return ts


def main():
    verify_sha = "--verify-sha" in sys.argv
    cli = connect()
    print("[ssh] connected")
    rc, out, err = run_cmd(cli, "ls -la %s 2>&1 | head -20" % REMOTE_BASE)
    print("[remote base]\n" + out.strip()[:1500])
    env_before = remote_stat_env(cli)
    print("[env before]", env_before)

    ts = do_backup(cli)

    manifest = {}
    if os.path.exists(MANIFEST_OUT):
        with open(MANIFEST_OUT, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    sftp = cli.open_sftp()
    total_uploaded = 0
    for phase in ("app", "scripts", "dist"):
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

    # 清理 frontend-dist/assets 中本次未上传的陈旧 .js/.css（仅 assets 目录）
    rc, out, err = run_cmd(cli, "ls %s/frontend-dist/assets/ 2>/dev/null" % REMOTE_BASE)
    stale = []
    if rc == 0 and out.strip():
        for fn in out.strip().splitlines():
            fn = fn.strip()
            if not fn:
                continue
            if fn.endswith(".js") or fn.endswith(".css"):
                if "frontend-dist/assets/" + fn not in manifest.get("dist", {}):
                    stale.append(fn)
    for fn in stale:
        rc2, _, _ = run_cmd(cli, "rm -f '%s/frontend-dist/assets/%s'" % (REMOTE_BASE, fn))
        print("[cleanup] removed stale asset:", fn)
    if not stale:
        print("[cleanup] no stale assets")

    env_after = remote_stat_env(cli)
    print("[env after ]", env_after)
    if env_before != env_after:
        print("[FATAL] backend/.env changed during upload!")
        sys.exit(3)
    print("[env] untouched - OK")

    with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    if verify_sha:
        import random
        candidates = list(manifest.get("app", {}).keys()) + ["backend/requirements.txt", "backend/scripts/run_server.py"]
        sample = sorted(random.sample(candidates, min(4, len(candidates))))
        for k in sample:
            local_sha = manifest["app" if k.startswith("backend/app/") else "scripts"].get(k, {}).get("sha256")
            if not local_sha:
                local_sha = manifest["scripts"].get(k, {}).get("sha256")
            if not local_sha:
                continue
            rc, out, _ = run_cmd(cli, "sha256sum '%s/%s' 2>&1" % (REMOTE_BASE, k))
            remote_sha = out.strip().split()[0] if rc == 0 else "ERR:" + out.strip()
            match = "MATCH" if remote_sha == local_sha else "MISMATCH"
            print("[sha256 %s] %s local=%s remote=%s" % (match, k, local_sha[:12], remote_sha[:12]))

    sftp.close()
    cli.close()
    print("[done] total_uploaded=%d manifest=%s backup_ts=%s" % (total_uploaded, MANIFEST_OUT, ts))


if __name__ == "__main__":
    main()
