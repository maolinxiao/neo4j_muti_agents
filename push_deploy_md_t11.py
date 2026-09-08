# -*- coding: utf-8 -*-
"""把 P8.4（t10 查询侧覆盖上线 + t11 封闭验证与最终交付）记录追加到 DEPLOY.md（本地 + 服务器）。"""
import os
import paramiko

LOCAL = r"D:\python_workspace\neo4j_muti_agents\DEPLOY.md"
HOST = "118.24.185.45"
REMOTE = "/www/wwwroot/neo4j-agents/deploy/DEPLOY.md"

RECORD = """


## 2026-09 查询侧 kb5 上下文覆盖 LLM 回显（P8.4 上线记录，2026-09-02，deploy-qa）

### 本次改动（commit 89c7b9c5「fix: 查询侧 kb5 上下文覆盖 LLM 回显，原方信息回注封闭」，仅 rnd_workflow_orchestrator.py，21+/1-）
- `_run_formula_generation`：_run_step 之后调用 `_override_kb5_context_with_query_side(result, formula_contexts)` ——
  查询侧 enrich 后的 kb5 上下文覆盖 LLM 回显（服务端结构化数据优先）；LLM 回显另存 `_kb5_echo`（回显与结构化不同时）；
  查询侧为空则不覆盖。至此 t8 回注源闭环：`_first_kb5_context` 始终能拿到查询侧结构化数据。

### 上线（2026-09-02）
- 备份：`backups/pre-t11-override-20260902013130/app/services/rnd_workflow_orchestrator.py`。
- 上传：1 文件（77,210 B）sha256 MATCH；服务器 py_compile OK。
- 重启：面板 restart → run=true pid=1274567 listen=127.0.0.1:8000；/api/health 200（postgres/neo4j/llm_configured 全 true）；本次启动后 0 ERROR/Traceback。

### 封闭验证（本地单元级 verify_t10_closed_loop.py，3/3 PASS）
- t10 覆盖：LLM 散文回显被查询侧结构化替换，散文存 _kb5_echo → PASS。
- t8 回注闭环：LLM 只填 changes、name/source 为空 → 回注 name=四君子汤、source=方剂学各论、《太平惠民和剂局方》宋 → PASS。
- LLM 完全未填 → 同样回注查询侧值 → PASS。

### t11 真实 run（同一问题「把四君子汤改造成药食同源代餐粉」，run 35f97ee4-d305-42be-9db1-9b75e18885d5，completed 6/6）
- final_formula：人参/君药/3-9g、白术/臣药/6-12g、茯苓/佐药/9-15g、炙甘草/使药/3-6g（basis=原方配比解析），无占位符。
- original_formula：name=四君子汤、source=方剂学各论、《太平惠民和剂局方》宋（本次 LLM 自行填充；封闭验证证明 LLM 未填时亦可回注）。
- monarch_minister_summary 一致；summary_metrics={stepCount:6, formulaCount:1, replacementCount:3, graphSnapshotCount:4}；无 step 失败。
- 前端最终方案 tab：25/25 PASS；「原方依据」区块渲染完整（四君子汤（来源：方剂学各论、《太平惠民和剂局方》宋）+ 保留/替换表/删除）；
  console 0 错误；截图 .tmp-rnd-t3/shots/（t9_origin_formula_section.png = t11 run 状态）。

### 观察项（非阻塞，可选 t12）
- step2 持久化输出 payload 仍为 LLM 回显（t10 覆盖仅作用于内存中的下游数据流，_run_step 内部已 commit）：
  方剂生成面板的「原方依据」行来自 frontend 对 kb5_formula_context 的 Array.isArray 判断 → 回显散文时该面板回退显示 classic_reference（不报错）。
  如需彻底一致：可在 _run_step 返回前持久化覆盖后 payload（或覆盖后二次 commit）。
"""


def main():
    with open(LOCAL, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.rstrip("\n") + RECORD
    with open(LOCAL, "w", encoding="utf-8") as f:
        f.write(content)
    print("[local DEPLOY.md written]", len(content))
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(hostname=HOST, port=22, username="root", password="mmfh2025KS686", timeout=30, banner_timeout=30, auth_timeout=30)
    cli.exec_command("cp -p %s %s.bak-202609020135" % (REMOTE, REMOTE), timeout=30)
    import time
    time.sleep(1)
    sftp = cli.open_sftp()
    with sftp.open(REMOTE, "w") as f:
        f.write(content)
    sftp.close()
    _, out, _ = cli.exec_command("tail -c 200 %s" % REMOTE, timeout=60)
    print("[remote tail]", out.read().decode("utf-8", "replace")[-150:])
    cli.close()


if __name__ == "__main__":
    main()
