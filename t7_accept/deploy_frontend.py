# -*- coding: utf-8 -*-
"""t7 第二轮：前端 dist 部署脚本。
步骤：整目录备份 → 上传新 dist（index.html + 4 新 hash 资源）→ 清理旧 hash 资源
（保留清单 = index.html 引用 + 主包动态 import chunk + login-bg 三件套）→ 权限规范化 → 校验。
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
FD = f"{REMOTE_BASE}/frontend-dist"
LOCAL_DIST = r"D:\python_workspace\neo4j_muti_agents\frontend\dist"

UPLOAD = [
    "index.html",
    "assets/index-BVbhVAst.js",
    "assets/index-BnTlgyQe.css",
    "assets/HeroKnowledgeScene-lkNFM12D.js",
]
KEEP = {
    "index.html",
    "login-bg.mp4",
    "login-bg-poster.svg",
    "login-bg-still.png",
    "assets/index-BVbhVAst.js",
    "assets/index-BnTlgyQe.css",
    "assets/HeroKnowledgeScene-lkNFM12D.js",
    "assets/HeroKnowledgeScene-DVgML9Jm.css",
    "assets/showcase-3d-BbLLm7wP.js",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def run(cli, cmd, timeout=180):
    _, out, err = cli.exec_command(cmd, timeout=timeout)
    return out.read().decode(errors="replace"), err.read().decode(errors="replace")


def main():
    ts = time.strftime("%Y%m%d%H%M%S")
    backup_dir = f"{FD}.bak-{ts}"
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, banner_timeout=30, auth_timeout=30)

    # 1) 备份当前前端目录
    o, e = run(cli, f"cp -a {FD} {backup_dir} && ls {backup_dir}/assets | wc -l && echo BACKUP_OK")
    print(o.strip(), e.strip()[:200])
    if "BACKUP_OK" not in o:
        print("[abort] 前端备份失败")
        cli.close()
        sys.exit(1)

    # 2) 上传新文件
    sftp = cli.open_sftp()
    for rel in UPLOAD:
        lp = os.path.join(LOCAL_DIST, rel)
        rp = f"{FD}/{rel}"
        sftp.put(lp, rp)
        print(f"[uploaded] {rel} ({os.path.getsize(lp)} B)")
    sftp.close()

    # 3) 清理旧 hash 资源（只保留 KEEP 清单）
    keep_cmds = " ".join(f"-name '{os.path.basename(k)}' -o" for k in KEEP)
    o, e = run(cli, f"cd {FD} && find assets -maxdepth 1 -type f ! \\( {keep_cmds} -name '__none__' \\) -print -delete")
    removed = [l for l in o.splitlines() if l.strip()]
    print(f"[cleanup] removed {len(removed)} stale assets:")
    for l in removed:
        print("  -", l)

    # 4) 权限规范化
    o, e = run(cli, f"find {FD} -type d -exec chmod 755 {{}} + && find {FD} -type f -exec chmod 644 {{}} + && echo CHMOD_OK")
    print(o.strip(), e.strip()[:200])

    # 5) 校验：index.html 引用 + 全部文件 sha256 对比 + 目录清单
    o, _ = run(cli, f"cat {FD}/index.html")
    print("[index.html]")
    print(o.strip())
    if "index-BVbhVAst.js" not in o or "index-BnTlgyQe.css" not in o:
        print("[abort] index.html 未引用新 bundle")
        cli.close()
        sys.exit(1)

    ok = True
    for rel in KEEP:
        lp = os.path.join(LOCAL_DIST, rel)
        if not os.path.exists(lp):
            print(f"[skip sha] {rel} 本地不存在（服务器保留项）")
            continue
        lsha = sha256_file(lp)
        so, _ = run(cli, f"sha256sum {FD}/{rel}")
        rsha = so.split()[0]
        status = "MATCH" if lsha == rsha else "MISMATCH"
        ok = ok and (lsha == rsha)
        print(f"[verify] {rel}: {status}")

    o, _ = run(cli, f"ls -la {FD}/assets/")
    print("[assets after deploy]")
    print(o.strip())

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend_backup_dir.txt"), "w") as fh:
        fh.write(backup_dir)
    cli.close()
    print("FRONTEND_DEPLOY_OK" if ok else "FRONTEND_DEPLOY_HAS_ERRORS")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
