# -*- coding: utf-8 -*-
"""T2 上线脚本（临时，勿提交）：特写内部展开重设计前端上线。
1) 回滚点：cp -r frontend-dist frontend-dist.bak-<ts>
2) 上传 frontend/dist/** -> /www/wwwroot/neo4j-agents/frontend-dist
3) 清理 assets 中未被新 index.html 引用的旧 hash .js/.css
4) 目录 755 / 文件 644 权限规范化
5) 校验新 index.html 与上传 manifest，输出线上资源清单
用法: python deploy_t2_upload.py [--verify-sha]
"""
import hashlib
import json
import os
import re
import sys

import paramiko

HOST = "118.24.185.45"
PORT = 22
USER = "root"
PASSWORD = "mmfh2025KS686"
REMOTE_BASE = "/www/wwwroot/neo4j-agents"
REMOTE_DIST = REMOTE_BASE + "/frontend-dist"
LOCAL_DIST = r"D:\python_workspace\neo4j_muti_agents\frontend\dist"
MANIFEST_OUT = r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\_deploy_manifest_t2.json"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def collect_local_tree(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
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


def main():
    verify_sha = "--verify-sha" in sys.argv
    cli = connect()
    print("[ssh] connected")

    rc, out, err = run_cmd(cli, "ls -la %s 2>&1 | head -30" % REMOTE_BASE)
    print("[remote base]\n" + out.strip()[:1500])

    # 0) 上线前快照：index.html 引用 + assets 清单
    rc, out, _ = run_cmd(cli, "cat %s/index.html 2>/dev/null" % REMOTE_DIST)
    old_html = out
    refs_before = sorted(set(re.findall(r'(?:src|href)="([^"]+)"', old_html)))
    print("[before] index.html refs:", refs_before)
    rc, out, _ = run_cmd(cli, "ls %s/assets/ 2>/dev/null" % REMOTE_DIST)
    assets_before = set(x.strip() for x in out.splitlines() if x.strip())
    print("[before] assets count:", len(assets_before))

    # 1) 回滚点
    rc, out, _ = run_cmd(cli, "cp -r %s %s.bak-$(date +%%Y%%m%%d%%H%%M%%S) && ls -d %s.bak-* | tail -1"
                         % (REMOTE_DIST, REMOTE_DIST, REMOTE_DIST))
    if rc != 0:
        print("[FATAL] backup failed:", out.strip(), _[:200])
        sys.exit(3)
    bak_dir = out.strip().splitlines()[-1].strip()
    print("[backup] rollback point:", bak_dir)

    # 2) 上传 dist
    files = collect_local_tree(LOCAL_DIST)
    manifest = {}
    sftp = cli.open_sftp()
    total = 0
    for abs_p, rel_p in files:
        remote_abs = REMOTE_DIST + "/" + rel_p
        ensure_remote_dir(sftp, os.path.dirname(remote_abs))
        sftp.put(abs_p, remote_abs)
        manifest[rel_p] = {"size": os.path.getsize(abs_p), "sha256": sha256_file(abs_p)}
        total += 1
    sftp.close()
    print("[upload] files=%d" % total)

    # 3) 新 index.html 引用
    rc, out, _ = run_cmd(cli, "cat %s/index.html" % REMOTE_DIST)
    new_html = out
    refs_after = sorted(set(re.findall(r'(?:src|href)="([^"]+)"', new_html)))
    print("[after] index.html refs:", refs_after)
    keep = set()
    for ref in refs_after:
        base = ref.split("?")[0].lstrip("./")
        keep.add(base.split("/")[-1])
    rc, out, _ = run_cmd(cli, "ls %s/assets/ 2>/dev/null" % REMOTE_DIST)
    assets_after = set(x.strip() for x in out.splitlines() if x.strip())
    stale = sorted(a for a in assets_after if a.endswith((".js", ".css")) and a not in keep)
    for fn in stale:
        run_cmd(cli, "rm -f '%s/assets/%s'" % (REMOTE_DIST, fn))
    print("[cleanup] removed stale assets:", stale if stale else "(none)")

    # 4) 权限规范化
    rc, out, _ = run_cmd(cli, "find %s -type d -exec chmod 755 {} + && find %s -type f -exec chmod 644 {} + && echo CHMOD_OK"
                         % (REMOTE_DIST, REMOTE_DIST))
    print("[chmod]", out.strip())

    # 5) 线上校验
    rc, out, _ = run_cmd(cli, "ls -la %s/ && echo --- && ls %s/assets/" % (REMOTE_DIST, REMOTE_DIST))
    print("[after ls]\n" + out.strip()[:2000])
    for ref in refs_after:
        rc, out, _ = run_cmd(cli, "test -f '%s/%s' && echo OK || echo MISSING" % (REMOTE_DIST, ref.split("?")[0].lstrip("./")))
        print("[asset check]", ref, "->", out.strip())

    with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump({"bak_dir": bak_dir, "refs_before": refs_before,
                   "refs_after": refs_after, "assets_before_count": len(assets_before),
                   "stale_removed": stale, "files": manifest},
                  f, ensure_ascii=False, indent=1)

    if verify_sha:
        import random
        sample = sorted(random.sample(list(manifest.keys()), min(4, len(manifest))))
        for k in sample:
            rc, out, _ = run_cmd(cli, "sha256sum '%s/%s' 2>&1" % (REMOTE_DIST, k))
            remote_sha = out.strip().split()[0] if rc == 0 else "ERR:" + out.strip()
            match = "MATCH" if remote_sha == manifest[k]["sha256"] else "MISMATCH"
            print("[sha256 %s] %s local=%s remote=%s" % (match, k, manifest[k]["sha256"][:12], remote_sha[:12]))

    # 取 admin 凭据（仅打印 username，密码只用于后续冒烟，不打印）
    rc, out, _ = run_cmd(cli, "grep -E '^DEFAULT_ADMIN_USERNAME=' %s/backend/.env | head -1 | cut -d= -f2-" % REMOTE_BASE)
    admin_user = out.strip()
    print("[creds] admin username:", admin_user)

    cli.close()
    print("[done] bak=%s manifest=%s" % (bak_dir, MANIFEST_OUT))


if __name__ == "__main__":
    main()
