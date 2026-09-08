# -*- coding: utf-8 -*-
"""T3 上线验收脚本：真实工作流跑通 + final_report/step/summary_metrics 检查。
密码从服务器 .env 读取，不回显。用法: python run_rnd_workflow_t3.py
"""
import base64
import io
import json
import os
import sys
import time

import paramiko
import requests

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageFont  # noqa: E402
from solve_captcha import CHARSET, crop_char, extract_char_boxes, load_mask, render_template  # noqa: E402

HOST = "118.24.185.45"
PORT = 22
USER = "root"
PASSWORD = "mmfh2025KS686"
BASE = "http://118.24.185.45/api"
FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captcha_input", "DejaVuSans.ttf")
QUESTION = "把四君子汤改造成药食同源代餐粉"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tmp-rnd-t3")
os.makedirs(OUT_DIR, exist_ok=True)


def read_env_creds():
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30, banner_timeout=30, auth_timeout=30)
    _, out, _ = cli.exec_command(
        "grep -E '^(DEFAULT_ADMIN_USERNAME|DEFAULT_ADMIN_PASSWORD)=' /www/wwwroot/neo4j-agents/backend/.env",
        timeout=60)
    data = out.read().decode("utf-8", "replace")
    cli.close()
    creds = {}
    for line in data.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            creds[k.strip()] = v.strip()
    return creds


def fetch_captcha():
    r = requests.get(BASE + "/auth/captcha", timeout=20)
    r.raise_for_status()
    d = r.json()
    png = base64.b64decode(d["image_base64"])
    img_path = os.path.join(OUT_DIR, "captcha.png")
    with open(img_path, "wb") as f:
        f.write(png)
    return d["captcha_id"], img_path


def _alpha_rows(tpl):
    px = tpl.load()
    w, h = tpl.size
    return [[px[x, y] for x in range(w)] for y in range(h)]


def _iou(a, b):
    inter = union = 0
    ha, wa = len(a), len(a[0])
    hb, wb = len(b), len(b[0])
    y0 = -(hb - ha) // 2 if hb >= ha else (ha - hb) // 2
    for y in range(ha):
        for x in range(wa):
            va = a[y][x]
            vb = 0
            by = y + y0
            if 0 <= by < hb and 0 <= x < wb:
                vb = b[by][x]
            if va and vb:
                inter += 1
                union += 1
            elif va or vb:
                union += 1
    return inter / union if union else 0.0


def ocr(path):
    """稳健 OCR：模板缩放至与裁剪同高、水平对中，逐字符 IoU 取最高。"""
    mask = load_mask(path)
    h = len(mask)
    w = len(mask[0])
    font = ImageFont.truetype(FONT, 28)
    segs = extract_char_boxes(mask, w, h)
    if len(segs) != 4:
        raise ValueError(f"segments={len(segs)} != 4, retry")
    text = []
    for (x0, x1) in segs:
        cm = crop_char(mask, w, h, x0, x1)
        bh = len(cm)
        bw = len(cm[0])
        best = (0.0, "?")
        for ch in CHARSET:
            tpl = render_template(font, ch)
            if tpl is None:
                continue
            tm = [[1 if p > 127 else 0 for p in row] for row in _alpha_rows(tpl)]
            th = len(tm)
            tw = len(tm[0])
            if th == 0 or tw == 0:
                continue
            scale = bh / th
            nw = max(1, int(round(tw * scale)))
            tpl2 = tpl.resize((nw, bh), Image.LANCZOS)
            tm2 = [[1 if p > 127 else 0 for p in row] for row in _alpha_rows(tpl2)]
            off = (bw - nw) // 2
            a = [[0] * bw for _ in range(bh)]
            for y in range(bh):
                for x in range(nw):
                    tx = x + off
                    if 0 <= tx < bw:
                        a[y][tx] = tm2[y][x]
            s = _iou(cm, a)
            if s > best[0]:
                best = (s, ch)
        text.append(best[1])
    return "".join(text)


def login(creds):
    for attempt in range(6):
        cid, img = fetch_captcha()
        try:
            code = ocr(img)
        except ValueError as exc:
            print(f"[ocr] retry: {exc}")
            continue
        r = requests.post(BASE + "/auth/login", json={
            "username": creds.get("DEFAULT_ADMIN_USERNAME", "admin"),
            "password": creds.get("DEFAULT_ADMIN_PASSWORD", ""),
            "captcha_id": cid,
            "captcha_text": code,
        }, timeout=20)
        if r.status_code == 200:
            tok = r.json().get("access_token") or r.json().get("token")
            print(f"[login] OK (attempt {attempt + 1})")
            return tok
        print(f"[login] attempt {attempt + 1} failed: {r.status_code} {r.text[:120]}")
        time.sleep(1)
    raise SystemExit("login failed")


def main():
    creds = read_env_creds()
    print("[creds] admin user =", creds.get("DEFAULT_ADMIN_USERNAME"), "(password read, not printed)")
    token = login(creds)
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(BASE + "/rnd/sessions", headers=headers, timeout=30)
    r.raise_for_status()
    session_id = r.json()["session_id"]
    print("[session]", session_id)

    r = requests.post(BASE + f"/rnd/sessions/{session_id}/runs", headers=headers,
                      json={"question": QUESTION, "reuse_last_brief": False}, timeout=30)
    print("[run create]", r.status_code)
    r.raise_for_status()
    run_id = r.json()["run_id"]
    print("[run]", run_id)

    deadline = time.time() + 600
    status = "queued"
    while time.time() < deadline:
        r = requests.get(BASE + f"/rnd/runs/{run_id}", headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        status = data.get("status")
        done = sum(1 for s in data.get("steps", []) if s.get("status") == "completed")
        total = len(data.get("steps", []))
        print(f"[poll] status={status} steps={done}/{total} elapsed={int(time.time() - data.get('started_at', time.time()))}s")
        if status in ("completed", "failed"):
            break
        time.sleep(5)

    with open(os.path.join(OUT_DIR, "run_result.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print("[saved] .tmp-rnd-t3/run_result.json")

    print("\n=== status ===", status)
    rep = data.get("final_report") or {}
    print("=== final_report keys ===", sorted(rep.keys()))
    ff = rep.get("final_formula") or {}
    comp = ff.get("composition") or []
    print("=== final_formula ===")
    print("name:", ff.get("name"))
    print("composition count:", len(comp))
    for it in comp:
        print("  -", {k: it.get(k) for k in ("name", "role", "dose", "basis", "source") if k in it})
    print("monarch_minister_summary:", json.dumps(rep.get("monarch_minister_summary"), ensure_ascii=False)[:600])
    print("original_formula:", json.dumps(rep.get("original_formula"), ensure_ascii=False)[:600])
    print("efficacy_summary:", json.dumps(rep.get("efficacy_summary"), ensure_ascii=False)[:400])
    print("flavor_summary:", json.dumps(rep.get("flavor_summary"), ensure_ascii=False)[:400])
    print("compliance_risks:", json.dumps(rep.get("compliance_risks"), ensure_ascii=False)[:400])
    print("evidence_gaps:", json.dumps(rep.get("evidence_gaps"), ensure_ascii=False)[:400])
    print("summary_metrics:", json.dumps(data.get("summary_metrics"), ensure_ascii=False))
    print("steps:")
    for s in data.get("steps", []):
        p = s.get("output_payload") or {}
        print(f"  [{s.get('sequence')}] {s.get('agent_key')} status={s.get('status')} payload_keys={sorted(p.keys())[:14]}")


if __name__ == "__main__":
    main()
