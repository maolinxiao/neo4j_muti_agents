# -*- coding: utf-8 -*-
"""T3 远端核对：逐组对比 _deploy_manifest_t3.json 与远端实际文件数/字节数，列出多余文件。"""
import json
import os
import paramiko

HOST = "118.24.185.45"
PORT = 22
USER = "root"
PASSWORD = "mmfh2025KS686"
REMOTE_BASE = "/www/wwwroot/neo4j-agents"
LOCAL_ROOT = r"D:\python_workspace\neo4j_muti_agents"
MANIFEST_OUT = os.path.join(LOCAL_ROOT, "_deploy_manifest_t3.json")

cli = paramiko.SSHClient()
cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
cli.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30, banner_timeout=30, auth_timeout=30)


def run_cmd(cmd, timeout=300):
    _, stdout, stderr = cli.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    return rc, out, err


with open(MANIFEST_OUT, "r", encoding="utf-8") as f:
    manifest = json.load(f)

# 远端每个组的实际清单
remote_lists = {}
for group in ["app", "scripts", "data", "dist"]:
    rc, out, err = run_cmd("find %s -type f -printf '%%s|%%p\\n' 2>/dev/null" % REMOTE_BASE)
    lines = [ln for ln in out.splitlines() if "|" in ln]
    mapping = {}
    for ln in lines:
        size_s, path = ln.split("|", 1)
        rel = path[len(REMOTE_BASE) + 1:]
        mapping[rel] = int(size_s)
    remote_lists[group] = mapping

ok_all = True
group_summary = {}
for group in ["app", "scripts", "data", "dist"]:
    expected = manifest[group]
    actual = remote_lists[group]
    # 按 group 前缀过滤
    prefixes = {"app": "backend/app/", "scripts": None, "data": "data/", "dist": "frontend-dist/"}
    prefix = prefixes[group]
    if prefix:
        act = {k: v for k, v in actual.items() if k.startswith(prefix)}
    else:
        # scripts 组包含 backend/requirements.txt, backend/scripts/run_server.py, scripts/*
        act = {k: v for k, v in actual.items()
               if k in ("backend/requirements.txt", "backend/scripts/run_server.py")
               or k.startswith("scripts/")}
    exp_files = set(expected.keys())
    act_files = set(act.keys())
    missing = exp_files - act_files
    extra = act_files - exp_files
    size_mismatch = [k for k in exp_files & act_files if expected[k]["size"] != act[k]]
    exp_bytes = sum(expected[k]["size"] for k in expected)
    act_bytes = sum(act[k] for k in act_files)
    group_summary[group] = {
        "exp_files": len(exp_files), "act_files": len(act_files),
        "exp_bytes": exp_bytes, "act_bytes": act_bytes,
        "missing": sorted(missing), "extra": sorted(extra),
        "size_mismatch": sorted(size_mismatch),
    }
    if missing or extra or size_mismatch or (len(exp_files) != len(act_files)) or (exp_bytes != act_bytes):
        ok_all = False
    print("[%s] exp %d files / %d B | act %d files / %d B | missing=%d extra=%d size_mismatch=%d"
          % (group, len(exp_files), exp_bytes, len(act_files), act_bytes,
             len(missing), len(extra), len(size_mismatch)))
    if missing:
        print("  missing:", missing[:10])
    if extra:
        print("  extra:", extra[:10])
    if size_mismatch:
        print("  size_mismatch:", size_mismatch[:10])

# 远端全部文件 vs 清单
rc, out, err = run_cmd("find %s -type f -printf '%%s|%%p\\n' 2>/dev/null" % REMOTE_BASE)
all_remote = {}
for ln in out.splitlines():
    if "|" in ln:
        size_s, path = ln.split("|", 1)
        all_remote[path[len(REMOTE_BASE) + 1:]] = int(size_s)
manifest_keys = set()
for g, files in manifest.items():
    manifest_keys.update(files.keys())
others = {k: v for k, v in all_remote.items() if k not in manifest_keys}
print("[total remote files]", len(all_remote))
print("[files not in manifest] %d:" % len(others))
for k in sorted(others):
    print("   %12d  %s" % (others[k], k))

rc, out, err = run_cmd("stat -c '%s|%Y' " + REMOTE_BASE + "/backend/.env" + " 2>&1 || echo MISSING")
print("[backend/.env]", out.strip())

cli.close()
print("[VERIFY]", "PASS" if ok_all else "FAIL")
