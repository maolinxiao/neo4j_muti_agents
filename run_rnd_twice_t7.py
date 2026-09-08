# -*- coding: utf-8 -*-
"""T7 加固回归：同一问题连续跑 2 次真实工作流，各自保存结果并校验。"""
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_rnd_workflow_t3 import BASE, QUESTION, read_env_creds, login  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp-rnd-t3")


def run_once(creds, tag):
    token = login(creds)
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(BASE + "/rnd/sessions", headers=headers, timeout=30)
    r.raise_for_status()
    session_id = r.json()["session_id"]
    r = requests.post(BASE + f"/rnd/sessions/{session_id}/runs", headers=headers,
                      json={"question": QUESTION, "reuse_last_brief": False}, timeout=30)
    r.raise_for_status()
    run_id = r.json()["run_id"]
    print(f"[{tag}] run={run_id} session={session_id}")
    deadline = time.time() + 600
    status = "queued"
    while time.time() < deadline:
        rr = requests.get(BASE + f"/rnd/runs/{run_id}", headers=headers, timeout=30)
        rr.raise_for_status()
        data = rr.json()
        status = data.get("status")
        done = sum(1 for s in data.get("steps", []) if s.get("status") == "completed")
        failed = sum(1 for s in data.get("steps", []) if s.get("status") == "failed")
        total = len(data.get("steps", []))
        print(f"[{tag}] status={status} steps={done}/{total} failed_steps={failed}")
        if status in ("completed", "failed"):
            break
        time.sleep(5)
    out = os.path.join(OUT_DIR, f"run_{tag}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"[{tag}] saved {out}")
    return data, status


def validate(data, tag):
    rep = data.get("final_report") or {}
    results = []
    status_ok = data.get("status") == "completed" and len(data.get("steps", [])) == 6
    results.append((f"{tag} status=completed 6/6", status_ok, "status=%s steps=%d" % (data.get("status"), len(data.get("steps", [])))))
    no_failed_step = all(s.get("status") != "failed" for s in data.get("steps", []))
    results.append((f"{tag} 无 step failed", no_failed_step, ""))
    comp = (rep.get("final_formula") or {}).get("composition") or []
    results.append((f"{tag} composition 非空", len(comp) > 0, "count=%d" % len(comp)))
    role_ok = all(c.get("role") in ("君药", "臣药", "佐药", "使药", "配伍药") for c in comp)
    results.append((f"{tag} 角色∈君主佐使/配伍药", role_ok, json.dumps([c.get("role") for c in comp], ensure_ascii=False)))
    import re
    dose_ok = all(re.search(r"\d+\s*(?:g|克)", str(c.get("dose") or "")) for c in comp)
    results.append((f"{tag} 剂量含具体数值", dose_ok, json.dumps([c.get("dose") for c in comp], ensure_ascii=False)))
    mms = rep.get("monarch_minister_summary") or []
    mms_ok = isinstance(mms, list) and len(mms) > 0
    results.append((f"{tag} monarch_minister_summary 非空", mms_ok, json.dumps(mms, ensure_ascii=False)[:200]))
    orig = rep.get("original_formula") or {}
    orig_ok = bool(orig.get("name")) and bool(orig.get("source"))
    results.append((f"{tag} original_formula 有名称出处", orig_ok, json.dumps(orig, ensure_ascii=False)[:200]))
    mm = data.get("summary_metrics") or {}
    mm_ok = mm.get("stepCount") == 6
    results.append((f"{tag} summary_metrics 正常", mm_ok, json.dumps(mm, ensure_ascii=False)))
    keys = sorted(rep.keys())
    need = ["final_formula", "monarch_minister_summary", "original_formula", "compliance_risks", "evidence_gaps"]
    results.append((f"{tag} final_report 新键齐备", all(k in keys for k in need), "keys=%s" % keys))
    for item, ok, detail in results:
        print("[%s] %s | %s" % ("PASS" if ok else "FAIL", item, detail))
    return results


def main():
    creds = read_env_creds()
    all_results = []
    for tag in ("run1", "run2"):
        data, status = run_once(creds, tag)
        all_results.extend(validate(data, tag))
    fails = [r for r in all_results if not r[1]]
    print("[DONE] total=%d pass=%d fail=%d" % (len(all_results), len(all_results) - len(fails), len(fails)))
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    main()
