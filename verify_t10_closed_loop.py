# -*- coding: utf-8 -*-
"""t11 封闭验证：t10 覆盖逻辑 + 原方信息回注闭环（本地单元级，不连服务）。

场景复现：公式生成 LLM 把 kb5_formula_context 回显为散文 → t10 覆盖为查询侧结构化 →
_original_formula_section 在 LLM 缺 name/source 时回注查询侧值。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from app.services.rnd_workflow_orchestrator import RnDWorkflowOrchestrator  # noqa: E402

orch = RnDWorkflowOrchestrator.__new__(RnDWorkflowOrchestrator)
RESULTS = []


def result(item, ok, detail=""):
    RESULTS.append((item, ok, detail))
    print("[%s] %s | %s" % ("PASS" if ok else "FAIL", item, detail))
    return ok


QUERY_SIDE_CTX = [{
    "formula_name": "四君子汤",
    "sources": ["方剂学各论", "《太平惠民和剂局方》宋"],
    "props": {"ratio": "人参 9g 白术 9g 茯苓 9g 炙甘草 6g", "source": "《太平惠民和剂局方》宋"},
    "role_herbs": [
        {"name": "人参", "role_relation": "MONARCH_HERB"},
        {"name": "白术", "role_relation": "MINISTER_HERB"},
        {"name": "茯苓", "role_relation": "ASSISTANT_HERB"},
        {"name": "炙甘草", "role_relation": "GUIDE_HERB"},
    ],
    "ingredients": [
        {"name": "人参", "role": "君药", "dosage": "9g"},
        {"name": "白术", "role": "臣药", "dosage": "9g"},
        {"name": "茯苓", "role": "佐药", "dosage": "9g"},
        {"name": "炙甘草", "role": "使药", "dosage": "6g"},
    ],
}]

PROSE_ECHO = "四君子汤源自《太平惠民和剂局方》，原方组成：人参9g、白术9g、茯苓9g、炙甘草6g……（LLM 转述散文）"


def case_override():
    """t10：覆盖函数把 LLM 散文回显替换为查询侧数据，散文另存 _kb5_echo。"""
    result_payload = {
        "output_payload": {
            "formulas": [{"name": "候选方"}],
            "kb5_formula_context": PROSE_ECHO,
        }
    }
    out = RnDWorkflowOrchestrator._override_kb5_context_with_query_side(result_payload, QUERY_SIDE_CTX)
    op = out["output_payload"]
    ok = op.get("kb5_formula_context") == QUERY_SIDE_CTX and op.get("_kb5_echo") == PROSE_ECHO
    result("t10 覆盖：查询侧结构化替换 LLM 散文，散文存 _kb5_echo", ok,
           "ctx_is_query=%s echo_kept=%s" % (op.get("kb5_formula_context") == QUERY_SIDE_CTX, op.get("_kb5_echo") == PROSE_ECHO))


def case_backfill():
    """t8 回注闭环：LLM 只填 changes、name/source 为空时，从（已被 t10 覆盖的）查询侧 context 回注。"""
    formula_payload = {"formulas": [], "kb5_formula_context": QUERY_SIDE_CTX}
    value = {
        "name": "",
        "source": "",
        "changes": {
            "replaced": [{"from": "人参", "to": "黄芪", "score": 0.7559, "confidence": 0.6949}],
            "retained": ["茯苓"],
            "added": [],
            "removed": ["甘草"],
        },
    }
    out = orch._original_formula_section(value, formula_payload, None)
    ok = out.get("name") == "四君子汤" and "方剂学各论" in (out.get("source") or "") and "太平惠民和剂局方" in (out.get("source") or "")
    result("t8 回注闭环：name/source 恒有查询侧值", ok, "name=%r source=%r" % (out.get("name"), out.get("source")))


def case_no_echo():
    """无回显（LLM 输出空 context）：查询侧覆盖后仍应回注（t10 保证覆盖路径）。"""
    formula_payload = {"formulas": [], "kb5_formula_context": QUERY_SIDE_CTX}
    value = {"name": "", "source": "", "changes": {"replaced": [], "retained": [], "added": [], "removed": []}}
    out = orch._original_formula_section(value, formula_payload, None)
    ok = out.get("name") == "四君子汤"
    result("回注闭环：LLM 完全未填 name/source 亦有查询侧值", ok, "name=%r source=%r" % (out.get("name"), out.get("source")))


case_override()
case_backfill()
case_no_echo()
fails = [r for r in RESULTS if not r[1]]
print("[DONE] total=%d pass=%d fail=%d" % (len(RESULTS), len(RESULTS) - len(fails), len(fails)))
sys.exit(1 if fails else 0)
