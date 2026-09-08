# -*- coding: utf-8 -*-
"""
药食同源多智能体研发协同平台 — 10 页汇报 PPT（v3，基于国自然模板）
- 字体：微软雅黑（替代模板默认等线）
- 排版：简洁分栏 + 真实系统截图为主视觉
- 输出：D:\\工作\\多智能体-宋\\2026-8-26.pptx
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from PIL import Image, ImageDraw

# ---------------------------------------------------------------- palette
TITLE_BLUE = RGBColor(0x1F, 0x4E, 0x79)
MAIN       = RGBColor(0x44, 0x72, 0xC4)
LIGHT_BLUE = RGBColor(0x5B, 0x9B, 0xD5)
PALE       = RGBColor(0xDE, 0xEB, 0xF7)
PALE2      = RGBColor(0xF2, 0xF7, 0xFC)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
BORDER     = RGBColor(0xC9, 0xDC, 0xF0)
ORANGE     = RGBColor(0xED, 0x7D, 0x31)
TEXT       = RGBColor(0x33, 0x40, 0x52)
DIM        = RGBColor(0x6E, 0x7F, 0x94)
SHADOW     = RGBColor(0xE2, 0xE8, 0xF0)
FONT       = "Microsoft YaHei"

SW, SH = 13.333, 7.5
TEMPLATE = r"D:\PPT模板\国自然可用PPT\260128国自然.pptx"
OUT      = r"D:\工作\多智能体-宋\2026-8-26.pptx"
SHOTS    = r"D:\python_workspace\neo4j_muti_agents\outputs\screens_2026_08_26"
GRAPH_PNG = r"D:\工作\多智能体-宋\visualisation2.png"


def _set_ea(run, name):
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
    ea.set("typeface", name)


def _solid(shape, color):
    shape.fill.solid()
    shape.fill.fore_color.rgb = color


def _gradient(shape, c1, c2, angle=90):
    shape.fill.gradient()
    stops = shape.fill.gradient_stops
    stops[0].color.rgb = c1
    stops[0].position = 0.0
    stops[1].color.rgb = c2
    stops[1].position = 1.0
    shape.fill.gradient_angle = angle


def add_rect(slide, x, y, w, h, fill=None, line=None, line_w=1.0, shape=MSO_SHAPE.RECTANGLE, radius=None):
    sp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sp.adjustments[0] = radius
        except Exception:
            pass
    if fill is None:
        sp.fill.background()
    else:
        _solid(sp, fill)
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(line_w)
    sp.shadow.inherit = False
    return sp


def add_text(slide, x, y, w, h, lines, anchor=MSO_ANCHOR.TOP, wrap=True):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    for i, spec in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = spec.get("align", PP_ALIGN.LEFT)
        if spec.get("space_before") is not None:
            p.space_before = Pt(spec["space_before"])
        if spec.get("space_after") is not None:
            p.space_after = Pt(spec["space_after"])
        if spec.get("line_spacing") is not None:
            p.line_spacing = spec["line_spacing"]
        for (text, size, bold, color) in spec["runs"]:
            r = p.add_run()
            r.text = text
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color
            r.font.name = FONT
            _set_ea(r, FONT)
    return tb


def add_chip(slide, x, y, w, h, text, fill, tcolor=TEXT, size=10.5, bold=True):
    sp = add_rect(slide, x, y, w, h, fill=fill, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
    tf = sp.text_frame
    tf.word_wrap = False
    tf.margin_left = Inches(0.04)
    tf.margin_right = Inches(0.04)
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = tcolor
    r.font.name = FONT
    _set_ea(r, FONT)
    return sp


def add_arrow(slide, x, y, w, h, color=MAIN):
    return add_rect(slide, x, y, w, h, fill=color, shape=MSO_SHAPE.RIGHT_ARROW)


def num_badge(slide, x, y, d, text, fill=MAIN, size=13, color=WHITE):
    sp = add_rect(slide, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    tf = sp.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = True
    r.font.color.rgb = color
    r.font.name = FONT
    _set_ea(r, FONT)
    return sp


def shot_card(slide, img_path, x, y, w, caption=None, cap_color=TITLE_BLUE):
    """Screenshot with soft shadow + border + optional caption bar below."""
    im = Image.open(img_path)
    iw, ih = im.size
    h = w * ih / iw
    add_rect(slide, x + 0.035, y + 0.045, w, h, fill=SHADOW, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.03)
    add_rect(slide, x, y, w, h, fill=WHITE, line=BORDER, line_w=1.2, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.03)
    pic = slide.shapes.add_picture(img_path, Inches(x + 0.045), Inches(y + 0.045), Inches(w - 0.09), Inches(h - 0.09))
    if caption:
        bar = add_rect(slide, x, y + h + 0.08, w, 0.34, fill=PALE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5)
        tf = bar.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.12)
        tf.margin_top = 0
        tf.margin_bottom = 0
        p = tf.paragraphs[0]
        r = p.add_run()
        r.text = caption
        r.font.size = Pt(9.5)
        r.font.bold = True
        r.font.color.rgb = cap_color
        r.font.name = FONT
        _set_ea(r, FONT)
    return h


def add_header(slide, no, title, subtitle):
    add_rect(slide, 0.55, 0.55, 0.52, 0.52, fill=MAIN)
    tf = add_rect(slide, 0.55, 0.55, 0.52, 0.52, fill=MAIN).text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = 0
    tf.margin_right = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = f"{no:02d}"
    r.font.size = Pt(15)
    r.font.bold = True
    r.font.color.rgb = WHITE
    r.font.name = FONT
    _set_ea(r, FONT)
    add_text(slide, 1.28, 0.5, 9.8, 0.62, [{"runs": [(title, 22, True, TITLE_BLUE)]}])
    add_text(slide, 1.29, 1.05, 10.8, 0.3, [{"runs": [(subtitle, 10.5, False, DIM)]}])
    add_rect(slide, 0.55, 1.42, 12.23, 0.012, fill=LINE if False else RGBColor(0xDD, 0xE6, 0xF0))


def add_footer(slide, page):
    add_text(slide, 0.55, 7.12, 6, 0.26, [{"runs": [("药食同源多智能体研发协同平台", 8.5, False, DIM)]}])
    add_text(slide, 11.55, 7.12, 1.23, 0.26, [{"runs": [(f"{page:02d} / 10", 9, True, DIM)], "align": PP_ALIGN.RIGHT}])


def card(slide, x, y, w, h, fill=WHITE, line=BORDER, line_w=1.0):
    return add_rect(slide, x, y, w, h, fill=fill, line=line, line_w=line_w, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.045)


def make_circle_png(src, out, size=640):
    im = Image.open(src).convert("RGB")
    im = im.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out_im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out_im.paste(im, (0, 0), mask)
    out_im.save(out)


# ---------------------------------------------------------------- open template
prs = Presentation(TEMPLATE)


def clear_slides(prs):
    sldIdLst = prs.slides._sldIdLst
    for sld in list(sldIdLst):
        rId = sld.get(qn("r:id"))
        prs.part.drop_rel(rId)
        sldIdLst.remove(sld)


clear_slides(prs)
blank = prs.slide_layouts[6]
cover_lay = prs.slide_layouts[0]


def new_slide(layout=blank):
    return prs.slides.add_slide(layout)


CIRCLE_PNG = r"D:\python_workspace\neo4j_muti_agents\tmp_ppt_circle.png"
make_circle_png(GRAPH_PNG, CIRCLE_PNG)

# ================================================================ P1 cover
s = new_slide(cover_lay)
banner = add_rect(s, -0.05, -0.05, 13.45, 2.42, shape=MSO_SHAPE.RECTANGLE)
_gradient(banner, RGBColor(0x14, 0x36, 0x5E), RGBColor(0x3D, 0x6F, 0xB4), angle=90)
add_rect(s, -0.05, 2.35, 13.45, 0.045, fill=ORANGE)
add_text(s, 1.0, 0.55, 11.3, 0.42, [{"runs": [("AI  ·  知识图谱  ·  多智能体", 15, True, WHITE)], "align": PP_ALIGN.CENTER}])
add_text(s, 1.0, 1.02, 11.3, 0.75, [{"runs": [("药食同源多智能体研发协同平台", 32, True, WHITE)], "align": PP_ALIGN.CENTER}])
add_text(s, 1.0, 1.82, 11.3, 0.4, [{"runs": [("基于 Neo4j 知识图谱与 DeepSeek 大模型的医药人工智能应用", 13, False, RGBColor(0xD8, 0xE5, 0xF4))], "align": PP_ALIGN.CENTER}])

s.shapes.add_picture(CIRCLE_PNG, Inches(5.62), Inches(2.86), Inches(2.1), Inches(2.1))
add_rect(s, 5.62, 2.86, 2.1, 2.1, fill=None, line=RGBColor(0xAF, 0xC6, 0xE2), line_w=2, shape=MSO_SHAPE.OVAL)

add_text(s, 1.0, 5.2, 11.3, 0.45, [{"runs": [("知识问答工作台 · 研发协同工作台 · 8 大知识库 · 6 个研发 Agent", 14.5, True, TITLE_BLUE)], "align": PP_ALIGN.CENTER}])
add_rect(s, 4.92, 5.78, 3.5, 0.014, fill=RGBColor(0xC9, 0xD8, 0xE8))
add_text(s, 1.0, 5.98, 11.3, 0.4, [{"runs": [("汇报时间：2026 年 8 月 26 日", 12.5, False, DIM)], "align": PP_ALIGN.CENTER}])
add_text(s, 1.0, 6.52, 11.3, 0.35, [{"runs": [("让知识有图谱可依 · 让研发有证据可循 · 让合规有边界可守", 11, False, MAIN)], "align": PP_ALIGN.CENTER}])

# ================================================================ P2 background & pain
s = new_slide()
add_header(s, 2, "项目背景：药食同源产业的知识与合规挑战", "为什么需要一套“知识图谱 + 多智能体”的证据化平台")

card(s, 0.55, 1.7, 5.15, 4.9, fill=PALE2)
add_rect(s, 0.55, 1.7, 0.08, 4.9, fill=MAIN)
add_text(s, 0.9, 1.95, 4.6, 0.4, [{"runs": [("产业背景", 15, True, TITLE_BLUE)]}])
add_text(s, 0.9, 2.42, 4.55, 1.4, [
    {"runs": [("药食同源产业处于消费升级与合规监管并行的阶段：企业端需快速完成配方研发、风味优化与合规上市；个人端需基于自身体质获得可解释的食养与产品适配建议。", 11, False, TEXT)], "line_spacing": 1.35},
])
add_text(s, 0.9, 3.85, 4.6, 0.4, [{"runs": [("现状与机会", 15, True, MAIN)]}])
add_text(s, 0.9, 4.3, 4.55, 1.75, [
    {"runs": [("◆ 8 类知识库 + 消费者画像库已具备体系化数据基础", 10.5, False, TEXT)], "space_after": 5},
    {"runs": [("◆ 大模型具备自然语言理解与结构化生成能力", 10.5, False, TEXT)], "space_after": 5},
    {"runs": [("◆ 知识图谱为大模型回答提供可核验的证据链", 10.5, False, TEXT)], "space_after": 5},
    {"runs": [("◆ 企业研发与个人食养需要统一的证据化决策入口", 10.5, False, TEXT)], "space_after": 5},
])

pains = [
    ("知识分散", "8 类知识库散落在表格与文档中，检索与联动困难"),
    ("研发凭经验", "方剂改造与单味替代缺少量化评分与证据支撑"),
    ("合规复杂", "药食同源目录、GB2760/GB7718、宣传边界难核验"),
    ("食养无据", "体质辨识与产品适配缺乏个性化证据链与风险边界"),
]
px, py = 6.0, 1.7
pw, ph = 3.45, 2.34
for i, (t, d) in enumerate(pains):
    cx = px + (i % 2) * (pw + 0.2)
    cy = py + (i // 2) * (ph + 0.22)
    card(s, cx, cy, pw, ph, fill=WHITE)
    num_badge(s, cx + 0.25, cy + 0.22, 0.38, f"{i+1:02d}", fill=MAIN if i % 2 == 0 else LIGHT_BLUE, size=12)
    add_text(s, cx + 0.75, cy + 0.25, pw - 1.0, 0.4, [{"runs": [(t, 14, True, TITLE_BLUE)]}])
    add_text(s, cx + 0.28, cy + 0.78, pw - 0.55, 1.4, [{"runs": [(d, 10.5, False, DIM)], "line_spacing": 1.3}])
add_footer(s, 2)

# ================================================================ P3 positioning
s = new_slide()
add_header(s, 3, "平台定位：双工作台一体化的证据化平台", "知识问答与研发协同共用同一图谱底座，服务企业端与个人端")

card(s, 0.55, 1.7, 5.15, 4.15, fill=WHITE)
add_rect(s, 0.55, 1.7, 5.15, 0.07, fill=MAIN)
add_text(s, 0.9, 1.95, 4.5, 0.4, [{"runs": [("知识问答工作台", 15, True, TITLE_BLUE)]}])
qa_items = [
    ("个人端", "体质辨识 · 食养推荐 · 产品适配 · 禁忌风险"),
    ("企业端", "产品研发 · 方剂食品化 · 单味替代 · 风味市场"),
    ("体验", "SSE 流式回答 · 证据子图联动 · 五步过程摘要"),
]
for j, (k, v) in enumerate(qa_items):
    iy = 2.5 + j * 1.0
    add_chip(s, 0.9, iy, 0.85, 0.36, k, PALE, tcolor=TITLE_BLUE, size=9.5)
    add_text(s, 1.9, iy - 0.02, 3.7, 0.7, [{"runs": [(v, 9.5, False, TEXT)], "line_spacing": 1.15}])

card(s, 0.55, 6.05, 5.15, 0.62, fill=PALE)
add_text(s, 0.9, 6.2, 4.6, 0.35, [{"runs": [("安全：高危人群风险边界 · KB1/KB7 合规闸门 · 本地 fallback 兜底", 9, False, TEXT)]}])

shot_card(s, f"{SHOTS}\\04_chat_empty.png", 6.1, 1.7, 6.6, caption="知识问答工作台：输入问题，开始基于知识图谱的问答")
add_footer(s, 3)

# ================================================================ P4 architecture
s = new_slide()
add_header(s, 4, "系统总体架构：前端分层 + 双数据库 + LLM 统一接入", "Vue 3 前端经 axios / SSE 与 FastAPI 通信，PostgreSQL 记录业务，Neo4j 提供图谱证据")

layers = [
    ("前端层", 1.7, MAIN, [
        ("Vue 3 · Element Plus · Pinia", "Composition API · 状态管理 · 图谱可视化", 2.6, 5.2),
        ("axios + SSE 流式通信", "Bearer Token · token/evidence/graph 事件流", 8.0, 3.9),
    ]),
    ("后端层", 2.86, LIGHT_BLUE, [
        ("API Routes", "REST / SSE / 认证 / 后台任务", 2.6, 2.6),
        ("Services", "QA 编排 · RnD 工作流 · LLM 客户端", 5.35, 2.95),
        ("Repositories", "PostgreSQL CRUD · Neo4j Cypher", 8.45, 2.5),
    ]),
    ("数据层", 4.02, ORANGE, [
        ("PostgreSQL", "会话/消息/Prompt/工作流/QA Trace/体质档案（JSONB）", 2.6, 5.2),
        ("Neo4j", "KB1-KB8 + CDB1 图谱 · 证据子图召回 · 图指标", 8.0, 3.9),
    ]),
    ("AI 层", 5.18, RGBColor(0x54, 0x82, 0x35), [
        ("DeepSeekClient", "统一 LLM 客户端 · 结构化输出校验 · thinking 清洗 · 本地 fallback", 2.6, 5.2),
    ]),
]
for li, (lname, ly, lc, items) in enumerate(layers):
    add_rect(s, 0.55, ly, 0.24, 0.92, fill=lc, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.3)
    add_text(s, 0.93, ly + 0.3, 1.4, 0.4, [{"runs": [(lname, 11.5, True, lc)]}])
    for (t, d, ix, iw) in items:
        card(s, ix, ly, iw, 0.92, fill=WHITE if li % 2 == 0 else PALE2)
        add_text(s, ix + 0.2, ly + 0.1, iw - 0.4, 0.3, [{"runs": [(t, 11, True, TITLE_BLUE)]}])
        add_text(s, ix + 0.2, ly + 0.44, iw - 0.4, 0.4, [{"runs": [(d, 8.5, False, DIM)]}])
    if li < len(layers) - 1:
        add_arrow(s, 6.5, ly + 0.95, 0.45, 0.18, color=lc)

card(s, 0.55, 6.35, 12.23, 0.62, fill=PALE)
add_text(s, 0.9, 6.5, 11.6, 0.35, [{"runs": [("横切能力：Bearer Token 认证 · SSE 流式问答 · BackgroundTasks 异步工作流 · Prompt/Cypher 在线管理 · 全链路 QA Trace", 10, False, TEXT)]}])
add_footer(s, 4)

# ================================================================ P5 knowledge graph
s = new_slide()
add_header(s, 5, "知识图谱：0604 KB1-KB8 + CDB1 权威源", "全量重建自 6-4 最新数据源，不导入旧 Compound / 成分网络")

kbs = [
    ("KB1", "原料合法性"), ("KB2", "功效病症"), ("KB3", "风味评价"), ("KB4", "替代评分"),
    ("KB5", "名方方剂"), ("KB6", "产品市场"), ("KB7", "食品合规"), ("KB8", "体质食养"),
]
for i, (k, t) in enumerate(kbs):
    cx = 0.55 + (i % 4) * 1.78
    cy = 1.62 + (i // 4) * 1.02
    card(s, cx, cy, 1.68, 0.9, fill=WHITE)
    add_rect(s, cx, cy, 0.055, 0.9, fill=MAIN if i % 2 == 0 else LIGHT_BLUE)
    add_text(s, cx + 0.15, cy + 0.12, 1.4, 0.26, [{"runs": [(k, 9, True, MAIN)]}])
    add_text(s, cx + 0.15, cy + 0.4, 1.45, 0.3, [{"runs": [(t, 10.5, True, TITLE_BLUE)]}])

card(s, 0.55, 3.75, 7.28, 0.52, fill=PALE2)
add_text(s, 0.85, 3.87, 6.9, 0.3, [{"runs": [("CDB1 消费者画像与评论偏好库：产品画像 · 人群场景功效分组 · 京东/淘宝评论 · 风味/剂型偏好", 9.5, True, MAIN)]}])

shot_card(s, f"{SHOTS}\\06_graph_closeup.png", 0.55, 4.45, 6.6, caption="证据子图可视化：实体 · 关系 · 主路径（点击可核验）")

metrics = [("86,482", "节点总数"), ("207,354", "关系总数"), ("18", "节点类型"), ("30+", "关系类型")]
for i, (n, t) in enumerate(metrics):
    cx = 8.55 + (i % 2) * 2.1
    cy = 4.55 + (i // 2) * 1.15
    card(s, cx, cy, 1.95, 1.0, fill=PALE2)
    add_text(s, cx + 0.15, cy + 0.12, 1.7, 0.45, [{"runs": [(n, 18, True, MAIN if i % 2 == 0 else ORANGE)]}])
    add_text(s, cx + 0.15, cy + 0.6, 1.7, 0.3, [{"runs": [(t, 9, False, DIM)]}])

add_text(s, 8.55, 7.0, 4.2, 0.3, [{"runs": [("图谱口径：MERGE 幂等写入 · 人参分轨表达 · Flavor/NatureFlavor 严格区分", 8, False, DIM)]}])
add_footer(s, 5)
# ================================================================ P6 QA flow
s = new_slide()
add_header(s, 6, "知识问答：企业 / 个人分流 + 五步证据化回答", "qa_route 唯一细分路由入口，question_type 兼容旧模板与检索")

steps = ["任务分流", "核心信息检查", "KB 路由", "风险/合规边界", "回答与追问"]
step_colors = [MAIN, LIGHT_BLUE, ORANGE, RGBColor(0x54, 0x82, 0x35), TITLE_BLUE]
for i, st in enumerate(steps):
    cx = 0.55 + i * 1.06
    cy = 1.7 + i * 0.62
    num_badge(s, cx, cy, 0.34, str(i + 1), fill=step_colors[i], size=11)
    add_text(s, cx + 0.45, cy + 0.05, 1.3, 0.3, [{"runs": [(st, 10.5, True, TITLE_BLUE)]}])

card(s, 0.55, 4.85, 5.15, 1.95, fill=PALE2)
add_text(s, 0.85, 5.0, 4.6, 0.35, [{"runs": [("任务分流", 11.5, True, TITLE_BLUE)]}])
ent = ["产品研发", "方剂食品化", "单味替代", "风味剂型", "市场分析", "合规审查"]
for i, t in enumerate(ent):
    add_chip(s, 0.85 + (i % 2) * 2.15, 5.42 + (i // 2) * 0.44, 2.0, 0.36, t, WHITE, tcolor=TITLE_BLUE, size=9)
add_text(s, 0.85, 6.82, 4.7, 0.0, [{"runs": [("", 1, False, DIM)]}])

card(s, 0.55, 6.62, 5.15, 0.5, fill=PALE)
add_text(s, 0.85, 6.74, 4.7, 0.3, [{"runs": [("个人端：体质辨识 · 食养推荐 · 产品适配 · 风险边界", 9, False, TEXT)]}])

shot_card(s, f"{SHOTS}\\05b_chat_with_graph.png", 6.1, 1.7, 6.6, caption="问答回答 + 证据子图联动展示（黄精功效问答实例）")
add_footer(s, 6)

# ================================================================ P7 product development
s = new_slide()
add_header(s, 7, "产品研发：从名方溯源到配方草案的确定性链路", "graph_grounded 模式：检索完成后按小标题直接输出图谱答案")

chain = [("需求解析", MAIN), ("KB5 名方原型", LIGHT_BLUE), ("KB4 替代评分", ORANGE), ("配方草案", RGBColor(0x54, 0x82, 0x35)), ("风味剂型", LIGHT_BLUE), ("合规闸门", MAIN)]
for i, (t, c) in enumerate(chain):
    cx = 0.55 + i * 0.87
    cy = 1.72 + i * 0.62
    add_rect(s, cx, cy, 0.16, 0.16, fill=c, shape=MSO_SHAPE.OVAL)
    add_text(s, cx + 0.28, cy - 0.04, 1.6, 0.3, [{"runs": [(t, 10.5, True, TITLE_BLUE)]}])
    if i < len(chain) - 1:
        add_rect(s, cx + 0.14, cy + 0.2, 0.016, 0.36, fill=RGBColor(0xC9, 0xDC, 0xF0))

rules = [
    ("替换必须有直接证据", "实际“替换”必须存在 CAN_REPLACE 关系，无替代边只能标注为新增/删除或待核验"),
    ("100 分制双列展示", "KB4 原始分（换算 100 分制）与系统综合可信度分列，均为研发证据强度，不代表临床有效率"),
    ("证据性质分层", "直接图谱关系 → “图谱直接证据”；仅按功效/人群/风味筛选 → “系统推导的参考原型”"),
    ("小试假设标注", "成品比例与逐味用量标为研发小试起始范围，儿童/孕妇等不做默认目标人群"),
]
for i, (t, d) in enumerate(rules):
    cy = 4.05 + i * 0.74
    add_rect(s, 0.55, cy + 0.06, 0.12, 0.12, fill=ORANGE if i % 2 == 0 else MAIN, shape=MSO_SHAPE.OVAL)
    add_text(s, 0.8, cy - 0.03, 4.9, 0.3, [{"runs": [(t, 10.5, True, TITLE_BLUE)]}])
    add_text(s, 0.8, cy + 0.27, 4.95, 0.5, [{"runs": [(d, 8.5, False, DIM)], "line_spacing": 1.1}])

shot_card(s, f"{SHOTS}\\07_product_dev_answer.png", 6.1, 1.7, 6.6, caption="产品研发回答实例：四君子汤 → 药食同源代餐粉配方方案")
add_footer(s, 7)

# ================================================================ P8 rnd workflow
s = new_slide()
add_header(s, 8, "研发协同：六 Agent 顺序编排工作流", "固定顺序编排，每步独立 Agent + 独立步骤记录与图谱快照")

agents = [
    ("master_control", "需求拆解 · 模块调度 · 合规校验", MAIN),
    ("formula_generation", "组方设计 · 君臣佐使 · 剂量建模", LIGHT_BLUE),
    ("efficacy_prediction", "中医功效 · 现代药理 · 人群分层", ORANGE),
    ("flavor_prediction", "风味特征 · 协调性 · 优化建议", RGBColor(0x54, 0x82, 0x35)),
    ("replacement_mapping", "功效/风味/成本/合规替代方案", LIGHT_BLUE),
    ("master_control_final", "整合各模块 · 输出最终研发方案", MAIN),
]
for i, (key, desc, c) in enumerate(agents):
    cy = 1.72 + i * 0.66
    num_badge(s, 0.55, cy, 0.34, str(i + 1), fill=c, size=11)
    add_text(s, 1.05, cy - 0.02, 2.4, 0.3, [{"runs": [(key, 10, True, c)]}])
    add_text(s, 3.5, cy, 2.4, 0.35, [{"runs": [(desc, 8.5, False, DIM)]}])

card(s, 0.55, 5.85, 5.15, 1.0, fill=PALE2)
add_text(s, 0.85, 6.0, 4.6, 0.75, [
    {"runs": [("工程机制：", 10, True, TITLE_BLUE), ("BackgroundTasks 后台执行 · 每步 WorkflowStepRun + GraphSnapshot · 前端轮询 · LLM 失败本地兜底不中断", 9, False, TEXT)], "line_spacing": 1.2},
])

shot_card(s, f"{SHOTS}\\08_rnd_workspace.png", 6.1, 1.7, 6.6, caption="研发协同工作台：会话 · 运行状态 · 步骤结果")
add_footer(s, 8)

# ================================================================ P9 engineering
s = new_slide()
add_header(s, 9, "工程能力与验证：可解释 · 可维护 · 可验证", "从代码编译、前端构建、图谱统计到问答路由回归的多层验证体系")

rows = [
    ("可解释", MAIN, "QA Trace 留痕 · 证据子图回看 · 五步“图谱检索与证据整理摘要”可展示"),
    ("可维护", LIGHT_BLUE, "Prompt/Cypher 在线编辑 · 种子数据幂等 · 路由/Service/Repository 分层职责"),
    ("可验证", ORANGE, "py_compile · npm run build · validate_qa_routing 路由回归 · 图谱 dry-run 统计"),
]
for i, (t, c, d) in enumerate(rows):
    cy = 1.7 + i * 0.98
    card(s, 0.55, cy, 5.35, 0.84, fill=WHITE)
    add_rect(s, 0.55, cy, 0.07, 0.84, fill=c)
    add_text(s, 0.85, cy + 0.1, 1.15, 0.35, [{"runs": [(t, 13, True, TITLE_BLUE)]}])
    add_text(s, 0.85, cy + 0.44, 4.9, 0.35, [{"runs": [(d, 8.5, False, DIM)]}])

card(s, 0.55, 4.7, 5.35, 1.05, fill=PALE)
add_text(s, 0.85, 4.85, 4.9, 0.35, [{"runs": [("验收基线（0604 图谱 dry-run）", 11, True, TITLE_BLUE)]}])
add_text(s, 0.85, 5.22, 4.9, 0.45, [{"runs": [("86,482 节点 / 207,354 关系，Compound=0；五类验收问题均可路由到合理模板。", 8.5, False, TEXT)], "line_spacing": 1.15}])

card(s, 0.55, 5.95, 5.35, 1.0, fill=PALE2)
add_text(s, 0.85, 6.1, 4.9, 0.3, [{"runs": [("常用验证命令", 10.5, True, TITLE_BLUE)]}])
add_text(s, 0.85, 6.4, 4.9, 0.55, [{"runs": [("· validate_qa_routing.py 路由回归", 8.5, False, DIM)], "space_after": 2}, {"runs": [("· npm run build / py_compile / import_agent_kg_0604.py --dry-run", 8.5, False, DIM)]}])

shot_card(s, f"{SHOTS}\\09_admin_overview.png", 6.25, 1.7, 6.5, caption="管理后台数据概览：数据库健康 · 图谱统计 · 模板与工作流")
add_footer(s, 9)

# ================================================================ P10 summary
s = new_slide()
add_header(s, 10, "总结与展望", "以知识图谱为证据底座、以大模型为生成引擎的药食同源研发协同平台")

card(s, 0.55, 1.7, 5.95, 4.6, fill=WHITE)
add_rect(s, 0.55, 1.7, 5.95, 0.08, fill=MAIN)
add_text(s, 0.9, 1.95, 5.3, 0.4, [{"runs": [("项目成果", 15, True, TITLE_BLUE)]}])
sums = [
    ("图谱底座", "0604 KB1-KB8 + CDB1 全量重建，86,482 节点 / 207,354 关系，不依赖旧 Compound 网络"),
    ("问答双链路", "企业端 6 类 / 个人端 5 类任务分流，五步证据化回答 + 证据子图联动"),
    ("研发编排", "6 个研发 Agent 顺序编排，步骤级留痕与图谱快照，LLM 失败本地兜底"),
    ("安全合规", "KB1/KB7 合规闸门、高危人群风险边界、替换证据化、禁止系统视角措辞"),
]
for j, (t, d) in enumerate(sums):
    iy = 2.52 + j * 0.92
    add_text(s, 0.9, iy, 5.3, 0.32, [{"runs": [("■ " + t, 11.5, True, TITLE_BLUE)]}])
    add_text(s, 1.2, iy + 0.3, 5.05, 0.6, [{"runs": [(d, 9, False, TEXT)], "line_spacing": 1.15}])

card(s, 6.7, 1.7, 6.08, 4.6, fill=WHITE)
add_rect(s, 6.7, 1.7, 6.08, 0.08, fill=LIGHT_BLUE)
add_text(s, 7.05, 1.95, 5.3, 0.4, [{"runs": [("下一步展望", 15, True, TITLE_BLUE)]}])
outs = [
    ("工艺适配 Agent", "process_adaptation 独立化：剂型工艺、口感与稳定性建模"),
    ("市场预测 Agent", "market_prediction 独立化：竞品与价格带分析"),
    ("验证闭环", "感官小试、目标人群验证与合规文档自动回填"),
    ("Prompt 工程化", "Prompt 版本对比与效果评估，问答质量可量化回归"),
]
for j, (t, d) in enumerate(outs):
    iy = 2.52 + j * 0.92
    add_text(s, 7.05, iy, 5.3, 0.32, [{"runs": [("■ " + t, 11.5, True, TITLE_BLUE)]}])
    add_text(s, 7.35, iy + 0.3, 5.05, 0.6, [{"runs": [(d, 9, False, TEXT)], "line_spacing": 1.15}])

card(s, 0.55, 6.5, 12.23, 0.6, fill=PALE)
add_text(s, 0.9, 6.66, 11.6, 0.35, [{"runs": [("让知识有图谱可依、让研发有证据可循、让合规有边界可守 —— 谢谢观看", 12.5, True, TITLE_BLUE)], "align": PP_ALIGN.CENTER}])
add_footer(s, 10)


def card(slide, x, y, w, h, fill=WHITE, line=BORDER, line_w=1.0):
    return add_rect(slide, x, y, w, h, fill=fill, line=line, line_w=line_w, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.045)


prs.save(OUT)
import os
print("saved:", OUT)
print("slides:", len(prs.slides._sldIdLst))
print("size MB:", round(os.path.getsize(OUT) / 1024 / 1024, 1))
