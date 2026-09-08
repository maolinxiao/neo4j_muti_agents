# -*- coding: utf-8 -*-
"""检查 t7 两连跑 run1/run2 的 original_formula 与 kb5 上下文。"""
import json

for tag in ("run1", "run2"):
    with open(rf"D:\python_workspace\neo4j_muti_agents\.tmp-rnd-t3\run_{tag}.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    print("=" * 20, tag, data.get("run_id"), "=" * 20)
    steps = {s["agent_key"]: s for s in data.get("steps", [])}
    fg = steps["formula_generation"]["output_payload"]
    print("formula_generation kb5_formula_context type:", type(fg.get("kb5_formula_context")).__name__)
    ctx = fg.get("kb5_formula_context")
    if isinstance(ctx, list) and ctx and isinstance(ctx[0], dict):
        print("  ctx[0] keys:", sorted(ctx[0].keys()))
        print("  formula_name:", ctx[0].get("formula_name"), "| sources:", ctx[0].get("sources"))
    elif isinstance(ctx, str):
        print("  ctx str:", ctx[:150])
    formulas = fg.get("formulas") or []
    if formulas and isinstance(formulas[0], dict):
        print("  formulas[0].name:", formulas[0].get("name"))
    mcf = steps["master_control_final"]["output_payload"]
    print("master final original_formula:", json.dumps(mcf.get("original_formula"), ensure_ascii=False)[:400])
    print("final_report original_formula:", json.dumps((data.get("final_report") or {}).get("original_formula"), ensure_ascii=False)[:400])
