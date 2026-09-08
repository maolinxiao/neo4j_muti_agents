# -*- coding: utf-8 -*-
"""本地验证 t8 回注逻辑对「LLM 回显散文」场景是否有效（不连服务）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from app.services.rnd_workflow_orchestrator import RnDWorkflowOrchestrator  # noqa: E402


orch = RnDWorkflowOrchestrator.__new__(RnDWorkflowOrchestrator)


def run_case(label, kb5_value, expect_name):
    formula_payload = {"formulas": [], "kb5_formula_context": kb5_value}
    value = {
        "name": "",
        "source": "",
        "changes": {
            "replaced": [
                {"from": "人参", "to": "黄芪", "score": 0.7559, "confidence": 0.6949},
            ],
            "retained": [],
            "added": [],
            "removed": [],
        },
    }
    out = orch._original_formula_section(value, formula_payload, None)
    ok = out.get("name") == expect_name
    print(f"[{'PASS' if ok else 'FAIL'}] {label} name={out.get('name')!r} source={out.get('source')!r}")
    return ok


case_a = {
    "formula_name": "四君子汤",
    "sources": ["方剂学各论", "《太平惠民和剂局方》宋"],
    "ingredients": [],
}
ok_a = run_case("结构化 context（查询侧）", [case_a], "四君子汤")
prose = "四君子汤源自《太平惠民和剂局方》，原方组成：人参9g、白术9g、茯苓9g、炙甘草6g……"
ok_b = run_case("LLM 回显散文（t7 实证场景）", prose, "四君子汤")
print("SUMMARY:", "ALL_PASS" if ok_a and ok_b else "HAS_FAIL")
