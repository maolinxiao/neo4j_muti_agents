# -*- coding: utf-8 -*-
"""检查 run_result.json 中 formula_generation 与 master_control_final 的关键字段。"""
import json

with open(r"D:\python_workspace\neo4j_muti_agents\.tmp-rnd-t3\run_result.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for step in data.get("steps", []):
    if step["agent_key"] == "formula_generation":
        p = step["output_payload"]
        pf = p.get("formulas") or []
        print("=== formula_generation count =", len(pf))
        if pf:
            print("name:", pf[0].get("name"))
            print("ingredients:")
            print(json.dumps(pf[0].get("ingredients"), ensure_ascii=False, indent=1)[:2000])
            print("fang_jie:", str(pf[0].get("fang_jie"))[:300])
        print("kb5_formula_context:", json.dumps(p.get("kb5_formula_context"), ensure_ascii=False)[:1500])
    if step["agent_key"] == "master_control_final":
        p = step["output_payload"]
        print("=== master_control_final final_formula ===")
        print(json.dumps(p.get("final_formula"), ensure_ascii=False, indent=1)[:2000])
        print("=== monarch_minister_summary ===")
        print(json.dumps(p.get("monarch_minister_summary"), ensure_ascii=False)[:800])
