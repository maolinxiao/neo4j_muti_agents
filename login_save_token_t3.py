# -*- coding: utf-8 -*-
"""登录并将 token 保存到 .tmp-rnd-t3/token.txt（不回显）。"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_rnd_workflow_t3 import login, read_env_creds

creds = read_env_creds()
token = login(creds)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp-rnd-t3", "token.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write(token)
print("[saved token to]", out, "len=", len(token))
