# -*- coding: utf-8 -*-
"""把 P8.3（t8 回注上线 + t9 回归与发现）记录追加到 DEPLOY.md（本地 + 服务器）。"""
import os
import paramiko

LOCAL = r"D:\python_workspace\neo4j_muti_agents\DEPLOY.md"
HOST = "118.24.185.45"
REMOTE = "/www/wwwroot/neo4j-agents/deploy/DEPLOY.md"

RECORD = """


## 2026-09 original_formula 原方信息回注兜底（P8.3 上线记录，2026-09-02，deploy-qa）

### 本次改动（commit b8701321「fix: original_formula 原方信息查询侧回注」，仅 rnd_workflow_orchestrator.py）
- 新增 `_first_kb5_context`（取规范化后首个 kb5 context）与 `_kb5_source_text`（sources 优先、props.source 兜底）。
- `_original_formula_section`：LLM 输出仅填 changes 而缺 name/source 时，从 kb5_formula_context 回注 formula_name/source。

### 上线（2026-09-02）
- 备份：`backups/pre-t9-backfill-20260902012310/app/services/rnd_workflow_orchestrator.py`。
- 上传：1 文件（76,051 B）sha256 MATCH；服务器 py_compile OK。
- 重启：面板 restart → run=true pid=1272475 listen=127.0.0.1:8000；/api/health 200（postgres/neo4j/llm_configured 全 true）；本次启动后 0 ERROR/Traceback。

### t9 回归（同一问题「把四君子汤改造成药食同源代餐粉」，run f1f67288-9b07-4e1e-a926-4df718d51261，completed 6/6）
- final_formula：炙甘草/使药/6g、人参/君药/9g、白术/臣药/9g、茯苓/佐药/9g（basis=原方配比解析）；君臣佐使一览一致；summary_metrics={6,1,3,4}；无 step 失败。
- original_formula：name=四君子汤、source=方剂学各论、《太平惠民和剂局方》宋（本次 LLM 自行填充；changes：保留茯苓/替换3/删除甘草）。
- 前端最终方案 tab：25/25 PASS；「原方依据」区块渲染完整（名称/出处/保留/替换表/删除），截图 .tmp-rnd-t3/shots/t9_origin_formula_section.png。

### ⚠ 修复不完整（t8 判定 FAIL，建议 t10，非部署阻断）
- 单元级验证（verify_t8_backfill.py，直接调用 _original_formula_section）：
  - 结构化 kb5 context 场景：回注生效，name=四君子汤、source=方剂学各论、《太平惠民和剂局方》宋 → PASS；
  - **LLM 回显散文场景（t7 实证：约 2/3 概率出现）：_normalize_kb5_context 置空后回注源为空 → name/source 仍为空 → FAIL**。
- 根因：回注数据源取自 `formula_payload.kb5_formula_context`（即公式生成 LLM 回显字段），而非查询侧原始数据；LLM 将上下文转述为散文时该字段被 _normalize 置空，兜底失效。
- t10 建议：`_run_formula_generation` 中 `_run_step` 之后执行 `result["output_payload"]["kb5_formula_context"] = 查询侧 enrich 后的 formula_contexts`（服务端数据覆盖 LLM 回显），
  使 `_first_kb5_context`/`_composition_from_formula`/`_enrich_composition` 等下游始终拿到结构化 kb5 数据（名称/出处/role_herbs/ratio）。
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
    cli.exec_command("cp -p %s %s.bak-202609020125" % (REMOTE, REMOTE), timeout=30)
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
