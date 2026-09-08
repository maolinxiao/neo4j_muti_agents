# -*- coding: utf-8 -*-
"""T3 研发协同「证据与结果」面板前端验收（公网，Edge headless）。
用法: python accept_rnd_panel_t3.py [--url http://118.24.185.45] [--outdir .tmp-rnd-t3]
依赖 run_result.json（含 session_id/run_id/token?）——token 需从环境变量 T3_TOKEN 传入。
输出: <outdir>/shots/step_*.png + <outdir>/accept_report.json
"""
import argparse
import base64
import json
import os
import sys

from playwright.sync_api import sync_playwright

RESULTS = []


def result(item, ok, detail=""):
    RESULTS.append({"item": item, "ok": bool(ok), "detail": detail})
    print("[RESULT] %s | %s | %s" % ("PASS" if ok else "FAIL", item, detail))
    return bool(ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://118.24.185.45")
    ap.add_argument("--outdir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp-rnd-t3"))
    ap.add_argument("--token", default=os.environ.get("T3_TOKEN", ""))
    ap.add_argument("--runfile", default="run_result.json")
    args = ap.parse_args()

    # 读取工作流结果（含 session_id/run_id）
    result_path = os.path.join(args.outdir, args.runfile)
    with open(result_path, "r", encoding="utf-8") as f:
        run_data = json.load(f)
    session_id = run_data.get("session_id")
    run_id = run_data.get("run_id") or run_data.get("id")
    token = args.token or os.environ.get("T3_TOKEN", "")
    if not token or not session_id or not run_id:
        print("MISSING token/session/run")
        sys.exit(2)
    shots = os.path.join(args.outdir, "shots")
    os.makedirs(shots, exist_ok=True)

    console_errors = []
    page_errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
        ctx.add_init_script(
            "localStorage.setItem('ys_auth_token', %s);"
            "localStorage.setItem('ys_auth_user', JSON.stringify({username:'admin',role:'admin'}));"
            % json.dumps(token)
        )
        page = ctx.new_page()
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        url = f"{args.url}/app/rnd/{session_id}?runId={run_id}"
        print("[goto]", url)
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        # 等待 6 个步骤卡片
        page.wait_for_selector(".step-card", timeout=60000)
        n = page.locator(".step-card").count()
        result("步骤卡片数==6", n == 6, f"count={n}")

        # 等待 run completed
        for _ in range(40):
            status_tag = page.locator(".panel-card .el-tag").first.text_content() if page.locator(".panel-card .el-tag").count() else ""
            if "completed" in (status_tag or ""):
                break
            page.wait_for_timeout(1500)

        expected_tabs = {
            "主控 Agent": ["任务计划"],
            "方剂生成 Agent": ["配方组成"],
            "功效预测 Agent": ["功效评估"],
            "风味预测 Agent": ["风味评估"],
            "替代映射 Agent": ["替代对比"],
            "主控汇总 Agent": ["最终方案"],
        }
        content_checks = {
            "主控 Agent": ["任务计划"],
            "方剂生成 Agent": ["君臣佐使", "原方依据", "药材", "角色", "剂量"],
            "功效预测 Agent": ["功效", "机制", "风险"],
            "风味预测 Agent": ["风味", "口感", "接受度"],
            "替代映射 Agent": ["替代对比", "原药材", "推荐替代"],
            "主控汇总 Agent": ["最终配方", "君臣佐使", "原方依据", "合规", "证据缺口", "下一步"],
        }
        # 从 run_result.json 确定哪些 step 有快照 → 期望出现/不出现证据图谱 tab
        step_by_agent = {}
        for s in run_data.get("steps", []):
            step_by_agent[s.get("agent_key")] = s
        agent_label_to_key = {
            "主控 Agent": "master_control",
            "方剂生成 Agent": "formula_generation",
            "功效预测 Agent": "efficacy_prediction",
            "风味预测 Agent": "flavor_prediction",
            "替代映射 Agent": "replacement_mapping",
            "主控汇总 Agent": "master_control_final",
        }

        for label, tabs_expected in expected_tabs.items():
            card = page.locator(".step-card", has_text=label).first
            card.click()
            page.wait_for_timeout(2500)
            tab_items = page.locator(".el-tabs__item")
            tab_labels = [t.text_content().strip() for t in tab_items.all()]
            ok = all(t in tab_labels for t in tabs_expected)
            # 检查该 Agent 的专属 tab 不出现其它 Agent 的主 tab
            other = {"主控 Agent": "最终方案", "方剂生成 Agent": "最终方案", "功效预测 Agent": "最终方案",
                     "风味预测 Agent": "最终方案", "替代映射 Agent": "最终方案", "主控汇总 Agent": "任务计划"}[label]
            ok = ok and (other not in tab_labels)
            result(f"[{label}] tabs={tabs_expected} 且无多余 tab", ok, f"labels={tab_labels}")
            # 内容检查
            content_text = page.locator(".tab-content").first.text_content() or ""
            missing = [k for k in content_checks[label] if k not in content_text]
            result(f"[{label}] 面板内容含 {content_checks[label]}", not missing, "missing=%s" % missing)
            page.screenshot(path=os.path.join(shots, f"step_{label}.png"), full_page=False)
            # 证据图谱 tab：仅 step 有 graph_snapshot_id 时出现（数据驱动）
            step_key = agent_label_to_key[label]
            has_snapshot = bool((step_by_agent.get(step_key) or {}).get("graph_snapshot_id") or
                                (step_by_agent.get(step_key) or {}).get("graph_snapshot"))
            graph_tab_present = "证据图谱" in tab_labels
            result(
                f"[{label}] 证据图谱tab出现==有快照({has_snapshot})",
                graph_tab_present == has_snapshot,
                f"labels={tab_labels}",
            )

        # ---- 主控汇总：配方表角色/剂量专项校验（t5 修复判定） ----
        card = page.locator(".step-card", has_text="主控汇总 Agent").first
        card.click()
        page.wait_for_timeout(2500)
        content_text = page.locator(".tab-content").first.text_content() or ""
        result("主控汇总 无占位符(角色未标注/剂量待…)", "角色未标注" not in content_text and "剂量待结合原方出处" not in content_text,
               "placeholder出现" if ("角色未标注" in content_text or "剂量待结合原方出处" in content_text) else "ok")
        import re as _re
        comp_section = page.locator(".tab-content .report-section", has_text="最终配方").first
        rows = comp_section.locator(".el-table__body-wrapper tbody tr")
        role_ok = True
        dose_ok = True
        rows_info = []
        for i in range(rows.count()):
            cells = rows.nth(i).locator("td")
            texts = [c.text_content().strip() for c in cells.all()]
            rows_info.append(texts[:4])
            role = texts[1] if len(texts) > 1 else ""
            dose = texts[2] if len(texts) > 2 else ""
            if role not in ("君药", "臣药", "佐药", "使药", "配伍药"):
                role_ok = False
            if not _re.search(r"\d+\s*(?:g|克)", dose or ""):
                dose_ok = False
        result("主控汇总 配方表角色∈{君/臣/佐/使/配伍药}", role_ok, "rows=%s" % rows_info)
        result("主控汇总 配方表剂量含具体数值(g/克)", dose_ok, "rows=%s" % rows_info)
        cards = page.locator(".tab-content .role-card")
        mms_info = []
        for i in range(cards.count()):
            c = cards.nth(i)
            mms_info.append((c.locator(".role-title").text_content().strip(),
                             c.locator(".role-herbs").text_content().strip()))
        mms_ok = all(t in ("君药", "臣药", "佐药", "使药", "配伍药") and h for t, h in mms_info)
        result("主控汇总 君臣佐使一览与角色一致", mms_ok, "cards=%s" % mms_info)
        page.screenshot(path=os.path.join(shots, "step_主控汇总 Agent_final.png"), full_page=False)

        # 无 console 错误（过滤 favicon 404）
        filtered = [e for e in console_errors if "favicon" not in e]
        result("console 无错误", not filtered, "errors=%s" % filtered[:5])
        result("无 pageerror", not page_errors, "errors=%s" % page_errors[:5])

        browser.close()

    with open(os.path.join(args.outdir, "accept_report.json"), "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)
    fails = [r for r in RESULTS if not r["ok"]]
    print("[DONE] total=%d pass=%d fail=%d" % (len(RESULTS), len(RESULTS) - len(fails), len(fails)))


if __name__ == "__main__":
    main()
