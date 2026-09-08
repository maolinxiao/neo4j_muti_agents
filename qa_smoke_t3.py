# -*- coding: utf-8 -*-
"""QA 知识问答接口公网冒烟：登录→建会话→非流式提问（孕妇/人参 风险边界）→检查返回。"""
import json
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = "http://118.24.185.45/api"
ROOT = os.path.dirname(os.path.abspath(__file__))
print("=== QA 冒烟 ===")
r = requests.get(BASE + "/chat/sessions", headers={"Authorization": "Bearer " + open(os.path.join(ROOT, ".tmp-rnd-t3", "token.txt")).read().strip()}, timeout=20)
print("GET /api/chat/sessions ->", r.status_code)
r = requests.post(BASE + "/chat/sessions", headers={"Authorization": "Bearer " + open(os.path.join(ROOT, ".tmp-rnd-t3", "token.txt")).read().strip()}, timeout=20)
print("POST /api/chat/sessions ->", r.status_code, r.json().get("session_id"))
sid = r.json()["session_id"]
r = requests.post(BASE + f"/chat/sessions/{sid}/messages", headers={"Authorization": "Bearer " + open(os.path.join(ROOT, ".tmp-rnd-t3", "token.txt")).read().strip()}, json={"question": "孕妇能不能吃人参？"}, timeout=180)
print("POST /api/chat/sessions/{sid}/messages ->", r.status_code)
if r.status_code == 200:
    d = r.json()
    print("conclusion:", str(d.get("conclusion"))[:300])
    if d.get("follow_up_questions"):
        print("follow_up:", json.dumps(d.get("follow_up_questions"), ensure_ascii=False)[:200])
    ok = bool(d.get("conclusion"))
    print("QA_RESPONSE_OK" if ok else "QA_RESPONSE_EMPTY")
else:
    print(r.text[:300])
