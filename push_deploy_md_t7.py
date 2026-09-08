# -*- coding: utf-8 -*-
"""把 P8.2（t6 容错加固上线 + t7 两连跑回归）记录追加到 DEPLOY.md（本地 + 服务器）。"""
import os
import paramiko

LOCAL = r"D:\python_workspace\neo4j_muti_agents\DEPLOY.md"
HOST = "118.24.185.45"
REMOTE = "/www/wwwroot/neo4j-agents/deploy/DEPLOY.md"

RECORD = """


## 2026-09 kb5_formula_context 类型容错加固（P8.2 上线记录，2026-09-02，deploy-qa）

### 本次改动（commit b3d413e1「fix: kb5_formula_context 类型容错，防工作流偶发崩溃」，仅 rnd_workflow_orchestrator.py）
- 新增 `_safe_list` / `_safe_dict` / `_normalize_kb5_context`（str→json.loads 尝试，失败置空并 logger.warning）。
- `_collect_formula_herbs` / `_formula_context_herb_names` / `_formula_fallback` / `_composition_from_formula` / `_enrich_composition` /
  `_final_formula_section` / `_original_formula_section` / `_efficacy_summary_section` / `_flavor_summary_section` /
  `_collect_compliance_risks` / `_collect_evidence_gaps` / 替代对比相关路径全部改为类型安全遍历（非 dict 项跳过）。
- summary_metrics 的 formulaCount/replacementCount 使用 _safe_list 计数。

### 上线（2026-09-02）
- 备份：`backups/pre-t7-harden-20260902010840/app/services/rnd_workflow_orchestrator.py`。
- 上传：1 文件（74,753 B）sha256 MATCH；服务器 py_compile OK。
- 重启：面板 restart → run=true pid=1268656 listen=127.0.0.1:8000；/api/health 200（postgres/neo4j/llm_configured 全 true）；本次启动后 0 ERROR/Traceback/迁移报错（t6 未改 seed，prompt 与 00:55 版本一致）。

### t7 两连跑回归（同一问题「把四君子汤改造成药食同源代餐粉」，连续 2 次）
- run1=04681036-a6eb-4c26-9e7c-4fe035df5641、run2=3abdd98e-dac7-498f-99ac-679336aa72d4：均 completed 6/6、无 step failed（此前 t5 回归第 1 次在 step3 概率崩溃，本次加固后不再崩溃）。
- final_formula.composition（run2）：人参/君药/3-9g、白术/臣药/6-12g、茯苓/佐药/9-15g、炙甘草/使药/3-6g，无占位符；monarch_minister_summary 与配方一致；summary_metrics={stepCount:6, formulaCount:1, replacementCount:3, graphSnapshotCount:4}。
- 前端抽查（公网 Edge headless，run2）：25/25 PASS；截图 .tmp-rnd-t3/shots/（step_主控汇总 Agent_final.png 等）。

### ⚠ 遗留观察项（建议下一轮 backend-agent 处理，非阻断）
- 两连跑中公式生成 LLM 都把 kb5_formula_context 重述为非 JSON 散文（如「四君子汤源自《太平惠民和剂局方》…」），
  `_normalize_kb5_context` 正确置空 → 不再崩溃；但主控汇总 LLM 的 original_formula 输出仅填 changes、name/source 为空，
  导致最终方案「原方依据」专属区块（名称+出处+保留/替换/新增/删除表）未渲染（t5 回归 run b14a3b48 中 LLM 返回结构化 context 时该区块正常）。
  建议：step2 完成后由服务端把**查询侧**的结构化 kb5 context 回注到 formula 输出 payload（替换 LLM 回显字段），
  并让 `_original_formula_section` 在 LLM 缺 name/source 时用回注数据兜底（name=四君子汤、source=方剂学各论/《太平惠民和剂局方》宋）。
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
    cli.exec_command("cp -p %s %s.bak-202609020115" % (REMOTE, REMOTE), timeout=30)
    import time
    time.sleep(1)
    sftp = cli.open_sftp()
    with sftp.open(REMOTE, "w") as f:
        f.write(content)
    sftp.close()
    _, out, _ = cli.exec_command("tail -c 220 %s" % REMOTE, timeout=60)
    print("[remote tail]", out.read().decode("utf-8", "replace")[-160:])
    cli.close()


if __name__ == "__main__":
    main()
