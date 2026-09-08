# -*- coding: utf-8 -*-
"""T4: venv 安装依赖（pillow 等）。"""
import paramiko

HOST = "118.24.185.45"
PIP = (
    "/www/server/pyporject_evn/neo4j-agents-backend/bin/python -m pip install "
    "-r /www/wwwroot/neo4j-agents/backend/requirements.txt "
    "-i https://mirrors.aliyun.com/pypi/simple/ --no-input"
)

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, port=22, username="root", password="mmfh2025KS686",
            timeout=30, banner_timeout=30, auth_timeout=30)

# 先看当前装的版本
_, out, err = cli.exec_command("/www/server/pyporject_evn/neo4j-agents-backend/bin/python -m pip show pillow 2>&1 | head -5", timeout=60)
print("[pillow before]")
print(out.read().decode("utf-8", "replace").strip()[:800])

_, stdout, stderr = cli.exec_command(PIP, timeout=900)
out_txt = stdout.read().decode("utf-8", "replace")
err_txt = stderr.read().decode("utf-8", "replace")
rc = stdout.channel.recv_exit_status()
print("[pip rc]", rc)
print("[pip stdout tail]\n" + out_txt[-3000:])
if err_txt.strip():
    print("[pip stderr tail]\n" + err_txt[-2000:])

_, out, err = cli.exec_command("/www/server/pyporject_evn/neo4j-agents-backend/bin/python -m pip show pillow 2>&1 | head -5", timeout=60)
print("[pillow after]")
print(out.read().decode("utf-8", "replace").strip()[:800])

cli.close()
sys_exit = 0 if rc == 0 else 1
import sys
sys.exit(sys_exit)
