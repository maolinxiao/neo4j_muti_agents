# -*- coding: utf-8 -*-
"""检查服务器字体环境（临时脚本）。"""
import paramiko

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(hostname="118.24.185.45", port=22, username="root", password="mmfh2025KS686",
            timeout=30, banner_timeout=30, auth_timeout=30)
cmd = (
    "fc-list 2>/dev/null | grep -iE 'arial|dejavu|simhei|msyh' | head -20; "
    "echo ---; "
    "ls /usr/share/fonts 2>/dev/null; "
    "echo ---; "
    "find /usr/share/fonts /usr/local/share/fonts -iname '*.tt[fc]' 2>/dev/null | head -40"
)
_, out, err = cli.exec_command(cmd, timeout=60)
print(out.read().decode("utf-8", "replace"))
print("[stderr]", err.read().decode("utf-8", "replace")[:500])
cli.close()
