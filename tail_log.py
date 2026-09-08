# -*- coding: utf-8 -*-
"""查看后端应用日志尾部（临时脚本）。"""
import sys
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(hostname="118.24.185.45", port=22, username="root", password="mmfh2025KS686",
            timeout=30, banner_timeout=30, auth_timeout=30)
paths = [
    "/www/wwwlogs/python/neo4j-agents-backend/error.log",
    "/www/wwwlogs/python/neo4j-agents-backend/app.log",
]
for p in paths:
    _, out, _ = cli.exec_command("tail -n 80 %s 2>&1 || echo NOFILE" % p, timeout=60)
    txt = out.read().decode("utf-8", "replace")
    print("===== %s =====" % p)
    print(txt[-6000:])
cli.close()
