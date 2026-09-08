# -*- coding: utf-8 -*-
"""定位并更新服务器 DEPLOY.md（追加 P6 记录，不做破坏性改动）。"""
import sys

import paramiko

HOST = "118.24.185.45"
PASSWORD = "mmfh2025KS686"


def main():
    section = open(r"D:\python_workspace\neo4j_muti_agents\.tmp-inner-check\deploy_md_section.md",
                   encoding="utf-8").read()
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username="root", password=PASSWORD, timeout=30)
    _, so, _ = cli.exec_command(
        'find /www/wwwroot/neo4j-agents -name "DEPLOY.md" 2>/dev/null', timeout=30)
    paths = [x.strip() for x in so.read().decode().splitlines() if x.strip()]
    print("found:", paths)
    if not paths:
        sys.exit(2)
    target = paths[0]
    sftp = cli.open_sftp()
    with sftp.open(target, "r") as f:
        content = f.read().decode("utf-8")
    if "2026-09 特写内部展开重设计" in content:
        print("section already present, skip append")
    else:
        new_content = content.rstrip("\n") + "\n\n\n" + section + "\n"
        with sftp.open(target, "w") as f:
            f.write(new_content.encode("utf-8"))
        print("appended, new size:", len(new_content.encode("utf-8")))
    # 校验
    with sftp.open(target, "r") as f:
        tail = f.read().decode("utf-8")[-600:]
    print("--- tail ---")
    print(tail)
    sftp.close()
    cli.close()


if __name__ == "__main__":
    main()
