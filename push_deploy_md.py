# -*- coding: utf-8 -*-
"""回写服务器 deploy/DEPLOY.md（临时脚本）。"""
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(hostname="118.24.185.45", port=22, username="root", password="mmfh2025KS686",
            timeout=30, banner_timeout=30, auth_timeout=30)
sftp = cli.open_sftp()
with open(r"D:\python_workspace\neo4j_muti_agents\deploy\DEPLOY.md", "rb") as f:
    data = f.read()
with sftp.open("/www/wwwroot/neo4j-agents/deploy/DEPLOY.md", "w") as f:
    f.write(data)
sftp.close()
cli.close()
print("[uploaded]", len(data), "bytes")
