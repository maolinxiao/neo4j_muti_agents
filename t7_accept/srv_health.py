# -*- coding: utf-8 -*-
"""t7: 后端重启后健康检查 + 启动日志核查。"""
import json
import time

import paramiko

HOST = "118.24.185.45"
USER = "root"
PASSWORD = "mmfh2025KS686"


def run(cli, cmd, timeout=120):
    _, out, err = cli.exec_command(cmd, timeout=timeout)
    return out.read().decode(errors="replace"), err.read().decode(errors="replace")


def main():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=22, username=USER, password=PASSWORD, timeout=30, banner_timeout=30, auth_timeout=30)
    ok_health = False
    detail = ""
    for i in range(10):
        o, _ = run(cli, "curl -s -m 10 http://127.0.0.1:8000/api/health")
        try:
            d = json.loads(o)
            if d.get("status") == "ok":
                ok_health = True
                detail = json.dumps(d, ensure_ascii=False)
                break
            detail = o[:200]
        except Exception:
            detail = o[:200]
        time.sleep(2)
    print("HEALTH:", "OK" if ok_health else "FAIL", detail)
    # 启动日志尾部
    o, _ = run(cli, "tail -40 /www/wwwlogs/python/neo4j-agents-backend/error.log")
    print("===== startup log tail =====")
    print(o)
    err_lines = [l for l in o.splitlines() if "Traceback" in l or "ERROR" in l.upper() and "ERROR" in l]
    print("ERROR_LINES:", len(err_lines))
    for l in err_lines[:10]:
        print(l)
    cli.close()
    print("HEALTH_CHECK_OK" if ok_health else "HEALTH_CHECK_FAIL")


if __name__ == "__main__":
    main()
