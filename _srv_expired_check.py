# -*- coding: utf-8 -*-
"""服务器侧直接验证已部署 captcha_service 各失败分支（临时脚本，勿提交）。
用部署 venv 的 Python 直接 import 已部署模块：
  1) TTL 过期 → expired
  2) 大小写不敏感 + 去空白：存 'AbC3'，提交 ' abc3 ' → ok
  3) 成功后再提交 → used
"""
import sys
import time

sys.path.insert(0, "/www/wwwroot/neo4j-agents/backend")

from app.services.captcha_service import (
    CAPTCHA_EXPIRED,
    CAPTCHA_OK,
    CAPTCHA_USED,
    CaptchaStore,
    _CaptchaRecord,
)

ok = True
store = CaptchaStore()

# 1) TTL 过期分支
cid, _img = store.issue(ip="127.0.0.1")
with store._lock:
    store._records[cid].expires_at = time.time() - 1
r = store.verify(cid, "zzzz", "127.0.0.1")
print("expired_branch:", r, "PASS" if r == CAPTCHA_EXPIRED else "FAIL")
ok = ok and r == CAPTCHA_EXPIRED

# 2) 大小写不敏感 + 去空白（模拟 issue 存 'AbC3'，用户提交 ' abc3 '）
store2 = CaptchaStore()
store2._records["t2"] = _CaptchaRecord(
    code_hash=store2._hash(store2._normalize("AbC3")),
    expires_at=time.time() + 60,
    ip="127.0.0.1",
)
r = store2.verify("t2", " abc3 ", "127.0.0.1")
print("case_insensitive_branch:", r, "PASS" if r == CAPTCHA_OK else "FAIL")
ok = ok and r == CAPTCHA_OK

# 3) used 分支：同 id 再提交
r = store2.verify("t2", "ABC3", "127.0.0.1")
print("used_branch:", r, "PASS" if r == CAPTCHA_USED else "FAIL")
ok = ok and r == CAPTCHA_USED

print("SERVER_BRANCH_ALL_PASS:", ok)
sys.exit(0 if ok else 1)
