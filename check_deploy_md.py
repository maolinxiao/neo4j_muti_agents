# -*- coding: utf-8 -*-
"""查看服务器 deploy 目录与远端 DEPLOY.md（临时脚本）。"""
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(hostname="118.24.185.45", port=22, username="root", password="mmfh2025KS686",
            timeout=30, banner_timeout=30, auth_timeout=30)
_, out, _ = cli.exec_command(
    "ls -la /www/wwwroot/neo4j-agents/deploy/ 2>/dev/null; echo ---; "
    "find /www/wwwroot/neo4j-agents -maxdepth 2 -iname 'DEPLOY*' 2>/dev/null; echo ---; "
    "find /www/wwwroot/neo4j-agents -maxdepth 2 -iname '*.md' 2>/dev/null | head -10",
    timeout=60)
print(out.read().decode("utf-8", "replace"))
cli.close()
