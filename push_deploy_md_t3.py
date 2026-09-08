# -*- coding: utf-8 -*-
"""把 P8 上线记录追加到 DEPLOY.md（本地 + 服务器 deploy/DEPLOY.md）。"""
import os
import paramiko

LOCAL = r"D:\python_workspace\neo4j_muti_agents\DEPLOY.md"
SRC = r"D:\python_workspace\neo4j_muti_agents\captcha_input\DEPLOY.md.server"
HOST = "118.24.185.45"
REMOTE = "/www/wwwroot/neo4j-agents/deploy/DEPLOY.md"

RECORD = """


## 2026-09 研发协同主控汇总报告化 + 证据与结果面板按 Agent 重构（P8 上线记录，2026-09-02）

### 本次改动（后端 + 前端）
- commit 0448cfb2「feat: 主控汇总 Agent 报告化与结构化配方输出（含 seed prompt/schema）」：
  `backend/app/db/seed_data.py` 新增 `RND_MASTER_FINAL_SCHEMA`（final_formula.composition 逐味 name/role/dose/rationale/basis/source、
  monarch_minister_summary、original_formula.changes 保留/替换/新增/删除、efficacy_summary、flavor_summary、compliance_risks、evidence_gaps），
  `rnd_master_control_final` prompt 改为「总结报告模式」（结论先行、证据可追溯、风险显式、下一步可执行）；
  `backend/app/services/rnd_workflow_orchestrator.py` 新增 `_assemble_final_report`（旧键兼容 + 结构化键优先取主控输出、缺失按模块 payload 抽取）、
  `_final_formula_section` / `_monarch_minister_summary` / `_original_formula_section` / `_efficacy_summary_section` / `_flavor_summary_section` 等。
- commit 6ffbe15f「feat: 研发协同证据与结果面板按 Agent 重构（含 dist）」：`frontend/src/views/portal/RndWorkspaceView.vue` 按 Agent 生成面板 tabs
  （主控=任务计划、方剂=配方组成+君臣佐使分组、功效=功效评估、风味=风味评估、替代=替代对比、主控汇总=最终方案），证据图谱 tab 仅在有快照 step 出现；
  `frontend/src/stores/rnd.js` 微调。

### 构建与上线（deploy-qa，2026-09-02）
- 上线前备份：`backups/pre-t3-rnd-report-20260902003356/app/db/seed_data.py`、`backups/pre-t3-rnd-report-20260902003356/app/services/rnd_workflow_orchestrator.py`（旧 sha256 记录于部署流程）；
  `frontend-dist.bak-20260902003356`（旧 assets 5 件：index-CDUurgba.js / index-AzZonmcz.css / HeroKnowledgeScene-BmkO4RJu.js / HeroKnowledgeScene-DVgML9Jm.css / showcase-3d-BbLLm7wP.js，已核验）。
- 上传：backend 2 文件（seed_data.py 32,744 B、rnd_workflow_orchestrator.py 65,245 B）sha256 均 MATCH；frontend-dist 4 文件
  （index.html / assets/index-DXeoezzh.js / assets/index-5F4MD3IX.css / assets/HeroKnowledgeScene-BOEHd5n6.js）sha256 均 MATCH；
  保留 HeroKnowledgeScene-DVgML9Jm.css、showcase-3d-BbLLm7wP.js（构建未变更）；清理旧资源 3 件（index-CDUurgba.js、index-AzZonmcz.css、HeroKnowledgeScene-BmkO4RJu.js）；
  权限规范化 755/644；backend/.env 未触碰。
- 重启：面板 PythonProjectControl restart → run=true, pid 1260310, listen 127.0.0.1:8000；启动日志「Application startup complete」无错误。
- 种子更新验证：prompt_template key='rnd_master_control_final' updated_at=2026-09-02 00:34(+08)（种子"存在则更新"路径），
  system_prompt 含「总结报告」模式，output_schema 含 final_formula / monarch_minister_summary 等新键（7 条 prompt 全表正常）。

### 验收（2026-09-02，deploy-qa）
- 真实工作流（admin 登录→POST /api/rnd/sessions→POST runs 问题「把四君子汤改造成药食同源代餐粉」→轮询 completed 6/6，run cd8ba932-d27c-47aa-8a13-4c96563300ee）：
  final_report 含全部新键（brief_summary/final_recommendation/consistency_checks/next_actions/task_plan/data_sources/final_formula/
  monarch_minister_summary/original_formula/efficacy_summary/flavor_summary/compliance_risks/evidence_gaps/modules）；
  final_formula.composition 4 味（炙甘草/人参/白术/茯苓）；original_formula 含 KB5 原方四君子汤/出处/保留替换新增删除；
  summary_metrics={stepCount:6, formulaCount:1, replacementCount:3, graphSnapshotCount:4}；6 个 step output_payload 关键字段齐全。
- 前端验收（公网 Edge headless，Playwright）：21/21 PASS —— 逐 Agent 点击 6 个步骤卡片，右侧面板 tabs 与内容均按 Agent 专属展示
  （主控=任务计划、方剂=配方组成+君臣佐使分组+原方依据、功效=功效评估、风味=风味评估、替代=替代对比+GNN/Baseline 双表、
  主控汇总=最终方案报告含最终配方/君臣佐使一览/原方依据/合规/证据缺口/下一步）；「最终方案」tab 仅主控汇总出现；
  证据图谱 tab 与有快照 step 完全一致（4 个 step）；console 零错误/零 pageerror；截图 `.tmp-rnd-t3/shots/`。
- 公网回归：`http://118.24.185.45/` 200 且引用新 bundle（index-DXeoezzh.js）；5 个资源全部 200；`/api/health` 200（postgres/neo4j/llm_configured 全 true）；
  登录冒烟 captcha→login→（token）PASS；QA 接口冒烟 GET/POST /api/chat/sessions 200、POST messages 200（返回结构化追问）；旧资源请求命中 SPA 回退（text/html，既有行为）。

### ⚠ 已知质量缺口（非阻塞上线，建议下轮处理）
- 主控汇总 final_formula.composition 的 role/dose 为占位符：「角色未标注」「剂量待结合原方出处与专业规范核定」（reason=None, basis=""）。
  根因链：图谱 KB5 context 已带 role_herbs（MONARCH_HERB/MINISTER_HERB/ASSISTANT_HERB/GUIDE_HERB）与配比文本（人参 9g 白术 9g 茯苓 9g 炙甘草 6g），
  但 `find_formulas_for_brief` 返回的 ingredients 中 IN_FORMULA 边 role 属性为「角色未标注」、dosage 为 null，方剂生成 Agent 与主控汇总 Agent 均沿用了该占位值。
  建议：neo4j_repository 侧把 role_relation 映射为君/臣/佐/使并写入组成条目（或注入建议剂量），并同步强化 step2/step6 prompt 的 role/dose 取值规范。

### 回滚点
- 后端：`cp backups/pre-t3-rnd-report-20260902003356/app/db/seed_data.py backend/app/db/`、`cp backups/pre-t3-rnd-report-20260902003356/app/services/rnd_workflow_orchestrator.py backend/app/services/` → 面板重启。
- 前端：`cp -a frontend-dist.bak-20260902003356/. frontend-dist/`（覆盖后旧 index.html 与旧资源即恢复）→ 无需重启（静态站）。
"""


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.rstrip("\n") + RECORD
    with open(LOCAL, "w", encoding="utf-8") as f:
        f.write(content)
    print("[local DEPLOY.md written]", len(content))

    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(hostname=HOST, port=22, username="root", password="mmfh2025KS686", timeout=30, banner_timeout=30, auth_timeout=30)
    # 服务器侧备份旧 DEPLOY.md 后覆盖
    cli.exec_command("cp -p %s %s.bak-202609020034" % (REMOTE, REMOTE), timeout=30)
    import time
    time.sleep(1)
    sftp = cli.open_sftp()
    with sftp.open(REMOTE, "w") as f:
        f.write(content)
    sftp.close()
    _, out, _ = cli.exec_command("tail -c 400 %s" % REMOTE, timeout=60)
    print("[remote tail]", out.read().decode("utf-8", "replace")[-300:])
    cli.close()


if __name__ == "__main__":
    main()
