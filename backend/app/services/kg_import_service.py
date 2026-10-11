# -*- coding: utf-8 -*-
"""管理端「数据导入」服务层（2026-10-12 新增）。

设计要点
- **不重写任何映射逻辑**：上传的表格按「规范文件名 + 工作表名」落到临时目录，直接调用
  `kg_import_core` 里现成的 `build_kb*` 构造函数，保证与全量导入（0604 脚本）行为一致。
  多文件/多工作表的 builder 依赖 `read_rows` 对缺失文件的宽容（缺失即跳过），因此一次只
  导入一个工作表也能正确工作。
- **先预览后写入**：解析校验 → 内存构图得到计划计数 → 探测图谱现状得到「新增/更新」拆分
  → 管理员确认 → 写库。写库时全部打批次标记，可选撤销。
- **原料引用**：KB5/KB6 等 builder 依靠「已存在的 Herb 名做子串匹配」建立原料关联。单表
  导入时内存图里没有原料，因此写入前会从数据库把现有 Herb 名预置进内存图（否则边会静默丢失）。
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from app.core.config import settings
from app.services import kg_import_core as core
from app.services.xlsx_reader import read_sheet_rows

TEMPLATE_DIR_NAME = "import_templates"
UPLOAD_SUBDIR = "imports"

CATEGORIES = ["原料类", "方剂与替代", "产品与市场", "合规与体质"]

# KB4 的同一份文件里，builder 会读多个工作表：上传其中之一时，其余工作表必须存在（可为空表）
# 否则解析器会因「工作表缺失」报错（文件在、工作表不在，read_rows 的宽容策略不适用）。
KB4_CO_SHEETS: dict[str, list[str]] = {
    "Top10_药食同源替换非药食同源": [
        "原非药食同源药材", "候选替代药材", "替换排名", "最终综合评分", "专业评分", "flavor大众接受度",
        "effect_level1相似度", "effect_level2相似度", "主治病症相似度", "性相似度", "味相似度",
        "归经相似度", "安全性评分", "候选替代来源", "推荐状态",
    ],
    "十八反十九畏规则库": ["药材A", "药材B", "规则类型", "规则说明"],
    "评分规则_详细": ["评分项", "权重", "使用字段", "计算逻辑", "外行解释"],
    "flavor接受度规则": ["药味/口感特征", "接受度分值", "原因"],
    "禁忌命中候选_已排除": [
        "原非药食同源药材", "候选替代药材", "替换排名", "最终综合评分", "推荐状态",
        "十八反十九畏命中类型", "十八反十九畏命中说明",
    ],
}


@dataclass(frozen=True)
class ImportType:
    key: str
    name: str
    category: str
    rel_path: str          # 相对 kb_root 的规范文件路径（同时决定落盘位置）
    sheet: str             # 工作表名（逐字匹配）
    builder: str           # kg_import_core 里的构造函数名
    primary_label: str     # 主体节点标签（预览与统计用）
    primary_key: str       # 主体节点唯一键
    columns: list[str]     # 模板表头（列名逐字匹配解析器）
    required: list[str]    # 必填列
    needs_herb_context: bool = False  # 是否依赖「图谱中已有原料」做子串匹配
    co_sheets: list[str] = field(default_factory=list)  # 同一文件里 builder 还会读的兄弟工作表（模板需带空表）
    note: str = ""

    @property
    def key_column(self) -> str:
        """行级唯一标识列（模板里的第一列，用于文件内重复检测与必填校验）。"""
        return self.required[0] if self.required else self.columns[0]


# --------------------------------------------------------------------------------------
# 数据契约：文件/工作表名与列名都取自 kg_import_core 现有的解析器，逐字一致
# --------------------------------------------------------------------------------------
IMPORT_TYPES: dict[str, ImportType] = {
    # ---- 原料类 ----
    "kb1_legality": ImportType(
        key="kb1_legality", name="原料合法性", category="原料类",
        rel_path="KB1_药食同源原料合法性库.xlsx", sheet="KB1_合法性库",
        builder="build_kb1_to_kb3", primary_label="Herb", primary_key="herb_name",
        columns=["herb_name", "is_food_homology", "目录来源", "是否有毒", "毒性等级", "孕妇禁忌", "使用注意"],
        required=["herb_name"],
        note="新建原料并写入合法性属性；孕妇禁忌会生成 Taboo 节点与 HAS_TABOO 关系。",
    ),
    "kb2_effects": ImportType(
        key="kb2_effects", name="原料功效病症", category="原料类",
        rel_path="KB2_功效-病症-性味归经库.xlsx", sheet="KB2_功效病症库",
        builder="build_kb1_to_kb3", primary_label="Herb", primary_key="herb_name",
        columns=["herb_name", "effect_level1", "effect_level2", "功效", "主治病症",
                 "nature", "flavor", "meridian", "contraindication", "usage_precautions"],
        required=["herb_name"],
        note="多值列用「；」或「,」分隔；会生成功效分类/功效/主治/性味/归经/禁忌等节点与关系。",
    ),
    "kb3_flavor": ImportType(
        key="kb3_flavor", name="原料风味评价", category="原料类",
        rel_path="KB3_风味评价库.xlsx", sheet="KB3_风味评价库",
        builder="build_kb1_to_kb3", primary_label="Herb", primary_key="herb_name",
        columns=["herb_name", "苦味风险", "涩感风险", "甜味贡献", "酸味贡献",
                 "草本/药味风险", "香气描述", "后味风险", "整体风味接受度",
                 "PungentDB_taste_type", "PungentDB_compound"],
        required=["herb_name"],
        note="风险/贡献类数值列按 0-1 或百分数填写；香气与 PungentDB 味型会生成风味节点。",
    ),
    # ---- 方剂与替代 ----
    "kb4_substitute": ImportType(
        key="kb4_substitute", name="单味药替代评分", category="方剂与替代",
        rel_path="KB4_药食同源_替换.xlsx", sheet="Top10_药食同源替换非药食同源",
        builder="build_kb4_replacements", primary_label="Herb", primary_key="herb_name",
        columns=["原非药食同源药材", "候选替代药材", "替换排名", "最终综合评分", "专业评分",
                 "flavor大众接受度", "effect_level1相似度", "effect_level2相似度", "主治病症相似度",
                 "性相似度", "味相似度", "归经相似度", "安全性评分", "候选替代来源", "推荐状态",
                 "原药材effect_level1", "原药材effect_level2", "原药材主治病症",
                 "原药材nature", "原药材flavor", "原药材meridian",
                 "候选effect_level1", "候选effect_level2", "候选主治病症",
                 "候选nature", "候选flavor", "候选meridian",
                 "候选使用注意", "候选contraindication"],
        required=["原非药食同源药材", "候选替代药材"],
        co_sheets=["十八反十九畏规则库", "评分规则_详细", "flavor接受度规则"],
        note="生成 CAN_REPLACE 关系（含各维度评分）；原药材会标记为 food_homology=否，候选标记为是。",
    ),
    "kb4_incompat": ImportType(
        key="kb4_incompat", name="配伍禁忌（十八反十九畏）", category="方剂与替代",
        rel_path="KB4_药食同源_替换.xlsx", sheet="十八反十九畏规则库",
        builder="build_kb4_rules_and_incompat", primary_label="Herb", primary_key="herb_name",
        columns=["药材A", "药材B", "规则类型", "规则说明"],
        required=["药材A", "药材B"],
        co_sheets=["Top10_药食同源替换非药食同源", "评分规则_详细", "flavor接受度规则"],
        note="生成双向 INCOMPATIBLE_WITH 关系；两侧原料需先导入（作为占位节点自动创建）。",
    ),
    "kb5_classic": ImportType(
        key="kb5_classic", name="名方/方剂（经典名方）", category="方剂与替代",
        rel_path="KB5_名方-名剂知识库/100经典名方-处理过.xlsx", sheet="Sheet1",
        builder="build_kb5_formulas", primary_label="Formula", primary_key="formula_name",
        columns=["prescription_name", "id", "source", "efficacy", "crowd", "taboo",
                 "monarch_herb", "minister_herb", "assistant_herb", "guide_herb",
                 "ingredients", "ratio"],
        required=["prescription_name"],
        needs_herb_context=True,
        note="君臣佐使与组成药材列需与图谱中的原料名一致，否则不会生成原料关系。",
    ),
    "kb5_tcmm": ImportType(
        key="kb5_tcmm", name="方剂（TCMM 3000 条）", category="方剂与替代",
        rel_path="KB5_名方-名剂知识库/TCMM_3000条.xlsx", sheet="方剂数据",
        builder="build_kb5_formulas", primary_label="Formula", primary_key="formula_name",
        columns=["名称", "TCMM ID", "出处", "药方", "适应症", "原始文本"],
        required=["名称"], needs_herb_context=True,
        note="中药大辞典类方剂，以「名称」作为方剂唯一键。",
    ),
    "kb5_shanghan": ImportType(
        key="kb5_shanghan", name="方剂（伤寒论/方剂学）", category="方剂与替代",
        rel_path="KB5_名方-名剂知识库/方剂学_伤寒论.xlsx", sheet="方剂总表",
        builder="build_kb5_formulas", primary_label="Formula", primary_key="formula_name",
        columns=["方剂名", "一级分类", "二级分类", "组成", "功用", "主治", "来源", "附方", "补充依据/备注"],
        required=["方剂名"], needs_herb_context=True,
        note="以「方剂名」作为唯一键；组成药材需与图谱原料名一致才会建立关系。",
    ),
    # ---- 产品与市场 ----
    "kb6_product": ImportType(
        key="kb6_product", name="产品与市场", category="产品与市场",
        rel_path="KB6_产品与市场库.xlsx", sheet="KB6_产品与市场库",
        builder="build_kb6_products", primary_label="Product", primary_key="product_id",
        columns=["商品名", "品牌", "剂型", "配料", "卖点", "价格", "销量", "评论", "场景", "竞品功效标签"],
        required=["商品名"], needs_herb_context=True,
        note="产品唯一键由「品牌 + 商品名」生成；配料为空时会从商品名推断原料（边带 match_source）。",
    ),
    # ---- 合规与体质 ----
    "kb7_directory": ImportType(
        key="kb7_directory", name="药食同源目录", category="合规与体质",
        rel_path="KB7_食品标准合规库/01_药食同源目录.xlsx", sheet="药食同源目录",
        builder="build_kb7_compliance", primary_label="ComplianceRule", primary_key="rule_id",
        columns=["原料名称", "目录来源", "公告年份", "可食用部位", "使用限制", "安全限量/备注", "证据文件"],
        required=["原料名称"],
        note="写入目录合规规则并与原料关联（原料不存在时自动创建）。",
    ),
    "kb7_gb2760": ImportType(
        key="kb7_gb2760", name="GB2760 添加剂规则", category="合规与体质",
        rel_path="KB7_食品标准合规库/02_GB2760添加剂规则.xlsx", sheet="GB2760添加剂规则",
        builder="build_kb7_compliance", primary_label="ComplianceRule", primary_key="rule_id",
        columns=["规则对象", "功能类别", "适用范围", "最大使用量/残留量", "规则内容", "Agent检查点", "证据文件"],
        required=["规则对象"],
        note="规则唯一键由整行内容生成：修改任一单元格会生成新规则节点（旧规则保留）。",
    ),
    "kb7_gb7718": ImportType(
        key="kb7_gb7718", name="GB7718 标签规则", category="合规与体质",
        rel_path="KB7_食品标准合规库/03_GB7718标签规则.xlsx", sheet="GB7718标签规则",
        builder="build_kb7_compliance", primary_label="ComplianceRule", primary_key="rule_id",
        columns=["标签项目", "适用说明", "规则内容", "Agent检查点", "证据文件"],
        required=["标签项目"],
        note="同上：规则以整行内容为键。",
    ),
    "kb7_promotion": ImportType(
        key="kb7_promotion", name="普通食品宣传边界", category="合规与体质",
        rel_path="KB7_食品标准合规库/04_普通食品宣传边界.xlsx", sheet="普通食品宣传边界",
        builder="build_kb7_compliance", primary_label="ComplianceRule", primary_key="rule_id",
        columns=["边界类型", "规则内容", "允许/禁止", "依据", "风险等级", "Agent判断逻辑"],
        required=["边界类型"],
        note="同上：规则以整行内容为键。",
    ),
    "kb7_risk_expression": ImportType(
        key="kb7_risk_expression", name="禁用慎用表述", category="合规与体质",
        rel_path="KB7_食品标准合规库/05_禁用慎用表述.xlsx", sheet="禁用慎用表述",
        builder="build_kb7_compliance", primary_label="RiskExpression", primary_key="expression",
        columns=["表述", "类别", "风险说明", "建议替代表述", "风险等级", "依据"],
        required=["表述"],
        note="以「表述」为唯一键，写入风险表述节点及对应合规规则。",
    ),
    "kb8_constitution": ImportType(
        key="kb8_constitution", name="九种体质", category="合规与体质",
        rel_path="KB8_9种体质辨识与食养规则库/03_九种体质.xlsx", sheet="九种体质",
        builder="build_kb8_constitution", primary_label="ConstitutionType", primary_key="constitution_type_name",
        columns=["constitution_type", "constitution_id", "constitution_category", "main_feature",
                 "body_feature", "common_manifestations", "psychological_feature", "disease_tendency",
                 "environment_adaptability", "source_standard", "source_page", "agent_use"],
        required=["constitution_type"],
        note="体质唯一键为 constitution_type（九种体质各一行）。",
    ),
    "kb8_diet": ImportType(
        key="kb8_diet", name="体质食养方向", category="合规与体质",
        rel_path="KB8_9种体质辨识与食养规则库/04_体质-食养方向.xlsx", sheet="体质食养方向",
        builder="build_kb8_constitution", primary_label="ConstitutionType", primary_key="constitution_type_name",
        columns=["constitution_type", "diet_direction", "food_homology_direction",
                 "suitable_ingredient_examples", "product_form_suggestion", "scenario_suggestion",
                 "risk_control", "evidence_basis"],
        required=["constitution_type"], needs_herb_context=True,
        note="适宜原料列会生成 RECOMMENDS_HERB 关系；原料名需与图谱中已有原料一致，否则不会建立关系。",
    ),
    "kb8_caution": ImportType(
        key="kb8_caution", name="体质慎用原料", category="合规与体质",
        rel_path="KB8_9种体质辨识与食养规则库/05_体质慎用原料.xlsx", sheet="体质慎用原料",
        builder="build_kb8_constitution", primary_label="ConstitutionType", primary_key="constitution_type_name",
        columns=["constitution_type", "caution_category", "caution_ingredient_examples",
                 "caution_reason", "risk_level", "agent_action", "notes"],
        required=["constitution_type"], needs_herb_context=True,
        note="慎用原料列会生成 CAUTIONS_HERB 关系；原料名需与图谱中已有原料一致。",
    ),
}


# --------------------------------------------------------------------------------------
# 模板与文件落盘
# --------------------------------------------------------------------------------------
def template_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / TEMPLATE_DIR_NAME


def template_path(import_type: ImportType) -> Path:
    return template_dir() / f"{import_type.key}.xlsx"


def list_templates() -> list[dict[str, Any]]:
    out = []
    for item in IMPORT_TYPES.values():
        path = template_path(item)
        out.append({
            "key": item.key,
            "name": item.name,
            "category": item.category,
            "sheet": item.sheet,
            "columns": item.columns,
            "required": item.required,
            "note": item.note,
            "template_available": path.exists(),
            "template_size": path.stat().st_size if path.exists() else 0,
        })
    return out


def import_root(batch_id: str) -> Path:
    return Path(settings.upload_dir) / UPLOAD_SUBDIR / batch_id


def stage_upload(batch_id: str, import_type: ImportType, source_file: Path) -> Path:
    """把上传文件按「规范文件名 + 工作表名」落到批次临时目录，返回 kb_root。"""
    kb_root = import_root(batch_id) / "kb_root"
    target = kb_root / import_type.rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_file, target)
    return kb_root


# --------------------------------------------------------------------------------------
# 解析与校验（直接读上传的工作表，用于列/必填/重复校验）
# --------------------------------------------------------------------------------------
def read_uploaded_rows(source_file: Path, import_type: ImportType) -> list[dict[str, Any]]:
    try:
        return list(read_sheet_rows(source_file, import_type.sheet))
    except KeyError as exc:
        raise ValueError(
            f"工作表「{import_type.sheet}」不存在：请使用本站提供的模板填写，不要重命名工作表（当前工作表名见模板）"
        ) from exc


def validate_rows(import_type: ImportType, rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not rows:
        return {"row_count": 0, "errors": [{"row": None, "message": "表格没有数据行（仅表头或为空）"}], "warnings": warnings,
                "missing_columns": [], "extra_columns": []}

    headers = list(rows[0].keys())
    missing_columns = [c for c in import_type.required if c not in headers]
    if missing_columns:
        errors.append({"row": None, "message": f"缺少必填列：{'、'.join(missing_columns)}（列名需与模板完全一致）"})
    missing_optional = [c for c in import_type.columns if c not in headers and c not in import_type.required]
    if missing_optional:
        warnings.append({
            "row": None,
            "message": f"缺少可选列（这些列的数据不会被导入）：{'、'.join(str(c) for c in missing_optional[:10])}"
            + ("…" if len(missing_optional) > 10 else ""),
        })
    extra_columns = [c for c in headers if c not in import_type.columns and not str(c).startswith("column_")]
    if extra_columns:
        warnings.append({"row": None, "message": f"存在模板之外的列（将被忽略）：{'、'.join(extra_columns[:8])}"})

    key_column = import_type.key_column
    seen: dict[str, int] = {}
    empty_key_rows = 0
    for idx, row in enumerate(rows, start=2):  # 第 1 行是表头
        key_raw = row.get(key_column)
        key_value = key_raw.strip() if isinstance(key_raw, str) else key_raw
        if key_value in (None, ""):
            empty_key_rows += 1
            if len(errors) < 50:
                errors.append({"row": idx, "message": f"必填列「{key_column}」为空"})
            continue
        for column in import_type.required[1:]:
            value = row.get(column)
            if value is None or (isinstance(value, str) and not value.strip()):
                if len(errors) < 50:
                    errors.append({"row": idx, "message": f"必填列「{column}」为空"})
        if key_value in seen:
            if len(warnings) < 20:
                warnings.append({
                    "row": idx,
                    "message": f"与第 {seen[key_value]} 行的「{key_column}」重复，后出现的行会覆盖先出现的",
                })
        else:
            seen[key_value] = idx

    return {
        "row_count": len(rows),
        "errors": errors,
        "warnings": warnings,
        "missing_columns": missing_columns,
        "extra_columns": extra_columns,
        "empty_key_rows": empty_key_rows,
        "unique_keys": len(seen),
    }


# --------------------------------------------------------------------------------------
# 内存构图（复用核心 builder）+ 与图谱现状对比
# --------------------------------------------------------------------------------------
def _seed_herb_context(graph: core.GraphBuild, repo) -> int:
    """把数据库中已有的 Herb 名预置进内存图，使子串匹配能认出原料（否则相关边会静默丢失）。"""
    names: list[str] = []
    try:
        with repo.driver.session() as session:
            for record in session.run("MATCH (h:Herb) WHERE h.herb_name IS NOT NULL RETURN h.herb_name AS n"):
                if record["n"]:
                    names.append(record["n"])
    except Exception:
        return 0
    bucket = graph.nodes.setdefault("Herb", {})
    for name in names:
        bucket.setdefault(name, {"herb_name": name})
    return len(names)


def build_plan(import_type: ImportType, kb_root: Path, repo=None) -> core.GraphBuild:
    graph = core.GraphBuild()
    if import_type.needs_herb_context and repo is not None:
        _seed_herb_context(graph, repo)
    builder: Callable[[core.GraphBuild, Path], None] = getattr(core, import_type.builder)
    try:
        builder(graph, kb_root)
    except KeyError as exc:
        raise ValueError(
            f"模板不完整：缺少工作表 {exc}。请重新下载本数据类型的模板后填写（模板保留了解析所需的全部工作表）。"
        ) from exc
    return graph


def graph_summary(graph: core.GraphBuild) -> dict[str, Any]:
    node_counts = {label: len(records) for label, records in graph.nodes.items() if records}
    edge_counts: dict[str, int] = {}
    for (_sl, _s, rel_type, _el, _e) in graph.edges:
        edge_counts[rel_type] = edge_counts.get(rel_type, 0) + 1
    return {
        "planned_nodes": node_counts,
        "planned_edges": edge_counts,
        "total_nodes": sum(node_counts.values()),
        "total_edges": sum(edge_counts.values()),
    }


def preview(import_type: ImportType, graph: core.GraphBuild, repo, batch_id: str, mode: str) -> dict[str, Any]:
    """用数据库现状把「计划写入」拆成新增/更新，并生成覆盖模式所需的冲突快照。"""
    new_nodes = updated_nodes = 0
    new_edges = updated_edges = 0
    snapshot: list[dict[str, Any]] = []
    snapshot_fields = 0
    capped = False

    for label, records in graph.nodes.items():
        if not records:
            continue
        key_field = core.NODE_KEYS.get(label)
        if not key_field:
            continue
        keys = list(records.keys())
        existing = repo.probe_nodes(label, key_field, keys)
        for key, props in records.items():
            old = existing.get(key)
            if old is None:
                new_nodes += 1
                continue
            updated_nodes += 1
            changed: dict[str, Any] = {}
            for field_name, value in props.items():
                if value is None or value == "" or value == []:
                    continue
                if mode == "fill_empty":
                    if old.get(field_name) in (None, "", [], "待核验", "未知"):
                        changed[field_name] = None
                elif old.get(field_name) != value:
                    changed[field_name] = old.get(field_name)
            if changed:
                snapshot_fields += len(changed)
                if snapshot_fields > settings.import_snapshot_max:
                    capped = True
                    break
                snapshot.append({"label": label, "key_field": key_field, "key": key, "fields": changed})
        if capped:
            break

    edge_rows = [
        {"start_label": sl, "start_key": core.NODE_KEYS[sl], "start": s, "rel_type": rt,
         "end_label": el, "end_key": core.NODE_KEYS[el], "end": e, "props": props}
        for (sl, s, rt, el, e), props in graph.edges.items()
    ]
    existing_edges = repo.probe_edges(edge_rows) if edge_rows else set()
    for row in edge_rows:
        marker = (row["rel_type"], row["start"], row["end"])
        if marker in existing_edges:
            updated_edges += 1
        else:
            new_edges += 1

    return {
        "new_nodes": new_nodes,
        "updated_nodes": updated_nodes,
        "new_edges": new_edges,
        "updated_edges": updated_edges,
        "snapshot_entries": len(snapshot),
        "snapshot_fields": snapshot_fields,
        "snapshot_capped": capped,
        "snapshot_value": snapshot,
        "batch_id": batch_id,
        "mode": mode,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------------------
# 写库 / 撤销
# --------------------------------------------------------------------------------------
def commit_batch(import_type: ImportType, graph: core.GraphBuild, repo, batch_id: str, mode: str) -> dict[str, Any]:
    """按批次写库：先建约束，再写节点与关系，全部打批次标记。"""
    repo.ensure_constraints(core.NODE_KEYS)
    node_stats: dict[str, Any] = {}
    for label, records in graph.nodes.items():
        if not records:
            continue
        key_field = core.NODE_KEYS.get(label)
        if not key_field:
            continue
        rows = [{"key": key, "props": props} for key, props in records.items()]
        node_stats[label] = repo.merge_nodes(
            label, key_field, rows, batch_id=batch_id, mode=mode, batch_size=settings.import_batch_size
        )
    edge_rows = [
        {"start_label": sl, "start_key": core.NODE_KEYS[sl], "start": s, "rel_type": rt,
         "end_label": el, "end_key": core.NODE_KEYS[el], "end": e, "props": props}
        for (sl, s, rt, el, e), props in graph.edges.items()
    ]
    edge_stats = repo.merge_edges(edge_rows, batch_id=batch_id, mode=mode,
                                 batch_size=settings.import_batch_size) if edge_rows else {}
    return {
        "nodes": node_stats,
        "edges": edge_stats,
        "created_nodes": sum(v.get("created", 0) for v in node_stats.values()),
        "updated_nodes": sum(v.get("matched", 0) for v in node_stats.values()),
        "written_edges": edge_stats.get("rows", 0),
        "created_edges": edge_stats.get("created", 0),
        "updated_edges": edge_stats.get("matched", 0),
        "missing_edge_endpoints": edge_stats.get("missing_endpoints", 0),
        "mark": repo.count_batch(batch_id),
    }


def rollback_batch(repo, batch_id: str, snapshot: list[dict[str, Any]] | None) -> dict[str, Any]:
    """撤销：先按快照还原被补充/被覆盖的属性，再删本批次新增的边与孤立节点。"""
    restored = repo.restore_snapshot(snapshot or [])
    deleted_edges = repo.delete_batch_edges(batch_id)
    nodes = repo.delete_unreferenced_batch_nodes(batch_id)
    marks = repo.clear_batch_marks(batch_id)
    return {
        "restored_fields": restored,
        "deleted_edges": deleted_edges,
        "deleted_nodes": nodes.get("deleted", 0),
        "kept_referenced_nodes": nodes.get("kept_referenced", 0),
        "cleared_marks": marks,
    }
