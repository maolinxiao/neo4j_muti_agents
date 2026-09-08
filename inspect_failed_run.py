# -*- coding: utf-8 -*-
"""检查失败 run 的 formula_generation payload 中 kb5_formula_context 形状。"""
import json

with open(r"D:\python_workspace\neo4j_muti_agents\.tmp-rnd-t3\run_result.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for step in data.get("steps", []):
    if step["agent_key"] == "formula_generation":
        p = step["output_payload"]
        ctx = p.get("kb5_formula_context")
        print("kb5_formula_context type:", type(ctx).__name__)
        print("value:", json.dumps(ctx, ensure_ascii=False)[:800])
        print("formulas type:", type(p.get("formulas")).__name__)
        if isinstance(p.get("formulas"), list) and p.get("formulas"):
            print("formula[0].ingredients:", json.dumps(p["formulas"][0].get("ingredients"), ensure_ascii=False)[:600])
