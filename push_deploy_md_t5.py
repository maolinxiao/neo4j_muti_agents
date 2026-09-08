# -*- coding: utf-8 -*-
"""把 P8.1（t4 角色/剂量修复上线 + t5 回归）记录追加到 DEPLOY.md（本地 + 服务器）。"""
import os
import paramiko

LOCAL = r"D:\python_workspace\neo4j_muti_agents\DEPLOY.md"
HOST = "118.24.185.45"
REMOTE = "/www/wwwroot/neo4j-agents/deploy/DEPLOY.md"

RECORD = """


## 2026-09 配方角色/剂量占位修复（P8.1 上线记录，2026-09-02，deploy-qa）

### 本次改动（commit fa007555「fix: 配方君臣佐使与剂量来源映射修复，含 prompt 规范」）
- `backend/app/repositories/neo4j_repository.py`：新增 ROLE_RELATION_LABELS / map_role_relation（MONARCH_HERB→君药 等，占位符视为缺失）、
  clean_dose_value、parse_ratio_dosages（原方配比文本如「人参9g 白术9g 茯苓9g 炙甘草6g」→ {药材:剂量}）、
  enrich_formula_rows（find_formulas_for_brief 结果把 role_relation/原方君臣佐使字段/配比文本映射进 ingredients 的 role/dosage）。
- `backend/app/services/rnd_workflow_orchestrator.py`：配方 fallback 与组成抽取改用 map_role_relation/clean_dose_value（禁止占位符）；
  新增 `_enrich_composition`（composition 角色/剂量占位替换为图谱映射值或方剂学建议区间并附依据）、`_suggested_dose_for_herb`（人参 1-3g、君 6-9g、臣/佐 3-9g、使 1-3g）；
  `_final_formula_section` / `_monarch_minister_summary` 做角色归一。
- `backend/app/db/seed_data.py`：rnd_master_control_final / rnd_formula_generation prompt 增加 role 取值（君主佐使）与 dose（9g / 建议 9-15g）规范、禁止「角色未标注」「剂量待核定」。

### 上线（2026-09-02）
- 备份：`backups/pre-t5-role-dose-fix-20260902005459/app/{db,services,repositories}`（3 文件）。
- 上传：3 文件（seed_data.py 33,831 B / rnd_workflow_orchestrator.py 70,754 B / neo4j_repository.py 94,030 B）sha256 均 MATCH；服务器 py_compile OK。
- 重启：面板 restart → run=true pid=1265330 listen=127.0.0.1:8000；/api/health 200（postgres/neo4j/llm_configured 全 true）；本次启动后 0 ERROR/Traceback。
- 种子：rnd_formula_generation 与 rnd_master_control_final updated_at=2026-09-02 00:55(+08)，prompt 含 MONARCH_HERB→君药 映射与禁止占位符条款。

### t5 回归（同一问题「把四君子汤改造成药食同源代餐粉」，run b14a3b48-b359-49d5-981e-ed80cd4996e4，completed 6/6）
- final_formula.composition：炙甘草/使药/6g、人参/君药/9g、白术/臣药/9g、茯苓/佐药/9g（basis=原方配比解析，source=KB5 原方「四君子汤」）——占位符消除，PASS。
- monarch_minister_summary：使药=炙甘草/君药=人参/臣药=白术/佐药=茯苓，与 composition 一致，PASS。
- original_formula：KB5 原方四君子汤 + 出处 + changes（保留/替换/新增/删除），合规与证据缺口正常；summary_metrics={stepCount:6, formulaCount:1, replacementCount:3, graphSnapshotCount:4}。
- 前端最终方案 tab（公网 Edge headless）：25/25 PASS（配方表角色∈君主佐使、剂量含数值 6g/9g、君臣佐使一览一致、无占位符、console 0 错误）；截图 .tmp-rnd-t3/shots/step_主控汇总 Agent_final.png。

### ⚠ 遗留风险（建议下轮 hardening，非阻塞）
- 第一次回归运行（run 65c6c254）在 step3 失败：`_collect_formula_herbs` 对 `kb5_formula_context`（公式生成 LLM 输出）假设为 dict 数组，
  但 LLM 有时把该字段重述为字符串 → AttributeError: 'str' object has no attribute 'get' → 整 run failed（概率性）。
  已复测一次成功（6/6）后完成本记录；修复方向：`_run_formula_generation` 或 `_run_step` 输出处把 kb5_formula_context 规范化（仅保留 dict 项/丢弃字符串），
  并让 `_collect_formula_herbs` / `_formula_context_herb_names` / `_composition_from_formula` / `_enrich_composition` / `_final_formula_section` / `_original_formula_section` 对非 dict 项容错。
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
    cli.exec_command("cp -p %s %s.bak-202609020106" % (REMOTE, REMOTE), timeout=30)
    import time
    time.sleep(1)
    sftp = cli.open_sftp()
    with sftp.open(REMOTE, "w") as f:
        f.write(content)
    sftp.close()
    _, out, _ = cli.exec_command("tail -c 300 %s" % REMOTE, timeout=60)
    print("[remote tail]", out.read().decode("utf-8", "replace")[-200:])
    cli.close()


if __name__ == "__main__":
    main()
