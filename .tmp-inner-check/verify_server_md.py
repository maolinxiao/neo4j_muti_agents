# -*- coding: utf-8 -*-
"""校验服务器 DEPLOY.md 追加内容的 UTF-8 完整性。"""
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect("118.24.185.45", port=22, username="root", password="mmfh2025KS686", timeout=30)
_, so, _ = cli.exec_command(
    "grep -n '2026-09 特写内部展开重设计' /www/wwwroot/neo4j-agents/deploy/DEPLOY.md && "
    "grep -n 'HeroKnowledgeScene-x0ezEfm_' /www/wwwroot/neo4j-agents/deploy/DEPLOY.md && "
    "grep -n '教训' /www/wwwroot/neo4j-agents/deploy/DEPLOY.md", timeout=30)
out = so.read().decode("utf-8")
print(out)
cli.close()
