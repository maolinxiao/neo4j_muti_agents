import argparse
import csv
import json
import re
import sys
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator
import xml.etree.ElementTree as ET

BACKEND_VENDOR = Path(__file__).resolve().parents[1] / "backend" / "_vendor"
if BACKEND_VENDOR.exists():
    sys.path.insert(0, str(BACKEND_VENDOR))

from neo4j import GraphDatabase


NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
DEFAULT_DATA_DIR = Path(r"D:\工作\多智能体-宋\替代映射库-建模")
DEFAULT_FOOD_CSV = Path(r"D:\python_workspace\neo4j_muti_agents\origin_data\data_2\数据库\药食同源\中国药典中药材数据_106种药食同源.csv")
DEFAULT_FOOD_DOCX = Path(r"D:\python_workspace\neo4j_muti_agents\origin_data\data_2\数据库\经典名方\药食同源106种目录.docx")


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("\u0000", "")
    return text or None


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff_]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "unknown"


def herb_key(name: str) -> str:
    return f"herb:{slugify(name)}"


def ingredient_key(row: dict[str, Any]) -> str | None:
    for field in ("molecule_ID", "MOL_ID", "成分名称"):
        value = clean_text(row.get(field))
        if value:
            return f"ingredient:{slugify(value)}"
    return None


def compact_props(props: dict[str, Any]) -> dict[str, Any]:
    cleaned = {}
    for key, value in props.items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = value
            continue
        if isinstance(value, list):
            items = []
            for item in value:
                text = clean_text(item)
                if text and text not in items:
                    items.append(text)
            if items:
                cleaned[key] = items
            continue
        text = clean_text(value)
        if text is None:
            continue
        if re.fullmatch(r"-?\d+", text):
            cleaned[key] = text if len(text.lstrip("-")) > 18 else int(text)
        elif re.fullmatch(r"-?\d+\.\d+", text):
            cleaned[key] = float(text)
        else:
            cleaned[key] = text
    return cleaned


def shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(node.text or "" for node in item.findall(".//a:t", NS)) for item in root.findall("a:si", NS)]


def workbook_sheets(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    result = []
    for sheet in workbook.findall("a:sheets/a:sheet", NS):
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = rel_map[rel_id].lstrip("/")
        if target.startswith("xl/"):
            path = target
        else:
            path = f"xl/{target}"
        result.append((sheet.attrib["name"], path))
    return result


def col_index(cell_ref: str) -> int:
    letters = re.match(r"([A-Z]+)", cell_ref).group(1)
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - 64
    return value - 1


def read_sheet_rows(path: Path, sheet_name: str | None = None) -> Iterator[dict[str, Any]]:
    with zipfile.ZipFile(path) as zf:
        sst = shared_strings(zf)
        sheet_lookup = dict(workbook_sheets(zf))
        if sheet_name is None:
            _, sheet_path = next(iter(sheet_lookup.items()))
        else:
            sheet_path = sheet_lookup[sheet_name]
        root = ET.fromstring(zf.read(sheet_path))
        headers = None
        for row in root.findall(".//a:sheetData/a:row", NS):
            values: list[str] = []
            for cell in row.findall("a:c", NS):
                idx = col_index(cell.attrib.get("r", "A1"))
                while len(values) <= idx:
                    values.append("")
                cell_type = cell.attrib.get("t")
                v_node = cell.find("a:v", NS)
                is_node = cell.find("a:is", NS)
                if cell_type == "s" and v_node is not None and v_node.text is not None:
                    value = sst[int(v_node.text)]
                elif cell_type == "inlineStr" and is_node is not None:
                    value = "".join(node.text or "" for node in is_node.findall(".//a:t", NS))
                else:
                    value = v_node.text if v_node is not None else ""
                values[idx] = value
            if headers is None:
                headers = [clean_text(item) or f"column_{idx}" for idx, item in enumerate(values)]
                continue
            row_map = {header: values[idx] if idx < len(values) else "" for idx, header in enumerate(headers)}
            if any(clean_text(value) for value in row_map.values()):
                yield row_map


@dataclass
class NodeRecord:
    key: str
    label: str
    props: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplacementEdge:
    source_key: str
    target_key: str
    props: dict[str, Any]


class Builder:
    def __init__(self) -> None:
        self.herbs: dict[str, NodeRecord] = {}
        self.ingredients: dict[str, NodeRecord] = {}
        self.efficacy_tags: dict[str, NodeRecord] = {}
        self.efficacy_categories: dict[str, NodeRecord] = {}
        self.herb_ingredient_edges: set[tuple[str, str]] = set()
        self.herb_tag_edges: set[tuple[str, str]] = set()
        self.tag_category_edges: set[tuple[str, str]] = set()
        self.replacement_edges: list[ReplacementEdge] = []
        self.baseline_by_herb: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def add_herb(self, name: str, **props: Any) -> str:
        key = herb_key(name)
        record = self.herbs.get(key)
        if record is None:
            record = NodeRecord(key=key, label="Herb")
            self.herbs[key] = record
        merged = compact_props(props)
        aliases = list(record.props.get("aliases", []))
        for alias in merged.pop("aliases", []):
            if alias not in aliases:
                aliases.append(alias)
        if aliases:
            record.props["aliases"] = aliases
        sources = list(record.props.get("sources", []))
        for source in merged.pop("sources", []):
            if source not in sources:
                sources.append(source)
        if sources:
            record.props["sources"] = sources
        for key_name, value in merged.items():
            if key_name not in record.props or record.props.get(key_name) in (None, "", [], "待校验"):
                record.props[key_name] = value
        record.props.setdefault("name", name)
        record.props.setdefault("key", key)
        return key

    def add_ingredient(self, row: dict[str, Any]) -> str | None:
        key = ingredient_key(row)
        if not key:
            return None
        record = self.ingredients.get(key)
        if record is None:
            record = NodeRecord(key=key, label="Ingredient")
            self.ingredients[key] = record
        props = compact_props(
            {
                "key": key,
                "name": row.get("成分名称"),
                "molecule_id": row.get("molecule_ID"),
                "mol_id": row.get("MOL_ID"),
                "ob": row.get("OB(%)"),
                "dl": row.get("DL"),
                "molecular_weight": row.get("分子量"),
                "alogp": row.get("alogp"),
                "h_bond_donor": row.get("氢键供体"),
                "h_bond_acceptor": row.get("氢键受体"),
                "smiles": row.get("SMILES"),
                "smiles_source": row.get("SMILES_source"),
                "smiles_query": row.get("SMILES_query"),
                "ecfp_valid": row.get("ECFP_valid"),
                "ecfp_bits": row.get("ECFP_bits"),
            }
        )
        for prop_name, value in props.items():
            if prop_name not in record.props or record.props.get(prop_name) in (None, ""):
                record.props[prop_name] = value
        return key

    def add_efficacy(self, tag_name: str, category_name: str | None = None, keywords: str | None = None, description: str | None = None) -> str:
        key = f"efficacy_tag:{slugify(tag_name)}"
        record = self.efficacy_tags.get(key)
        if record is None:
            record = NodeRecord(key=key, label="EfficacyTag")
            self.efficacy_tags[key] = record
        record.props.update(compact_props({"key": key, "name": tag_name, "keywords": keywords, "description": description}))
        if category_name:
            category_key = f"efficacy_category:{slugify(category_name)}"
            category = self.efficacy_categories.get(category_key)
            if category is None:
                category = NodeRecord(key=category_key, label="EfficacyCategory")
                self.efficacy_categories[category_key] = category
            category.props.update(compact_props({"key": category_key, "name": category_name}))
            self.tag_category_edges.add((key, category_key))
        return key


def parse_food_homology_docx(docx_path: Path) -> set[str]:
    if not docx_path.exists():
        return set()
    names: set[str] = set()
    with zipfile.ZipFile(docx_path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", ns):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns)).strip()
        if text:
            paragraphs.append(text)

    def split_items(line: str) -> list[str]:
        items: list[str] = []
        buffer: list[str] = []
        depth = 0
        for char in line:
            if char == "（":
                depth += 1
            elif char == "）" and depth > 0:
                depth -= 1
            if char == "、" and depth == 0:
                item = "".join(buffer).strip().strip("。")
                if item:
                    items.append(item)
                buffer = []
                continue
            buffer.append(char)
        tail = "".join(buffer).strip().strip("。")
        if tail:
            items.append(tail)
        return items

    def should_parse_paragraph(line: str) -> bool:
        if "、" not in line:
            return False
        if line.startswith(("一、", "二、", "三、")):
            return False
        if re.match(r"^\d+\.", line):
            return False
        return True

    def normalize_name(name: str) -> str | None:
        value = re.sub(r"\s+", "", name)
        value = value.strip("、，,；;。")
        return value or None

    def extract_aliases(alias_text: str) -> list[str]:
        if any(
            token in alias_text
            for token in ["限", "煲汤", "代茶饮", "产区", "/", "调味品", "公告", "干品≤", "传统方式"]
        ):
            if alias_text in {"甜", "苦"}:
                return [alias_text]
            return []
        aliases: list[str] = []
        for alias in re.split(r"[、，,]", alias_text):
            cleaned = normalize_name(alias)
            if cleaned and cleaned not in aliases:
                aliases.append(cleaned)
        return aliases

    for line in paragraphs:
        if not should_parse_paragraph(line):
            continue
        for raw_item in split_items(line):
            item = raw_item.strip().strip("。")
            if not item:
                continue
            if re.match(r"^\d+\.", item):
                item = re.sub(r"^\d+\.\s*", "", item)
            primary = normalize_name(re.sub(r"（.*?）", "", item))
            if primary:
                names.add(primary)
            for alias_text in re.findall(r"（(.*?)）", item):
                for alias in extract_aliases(alias_text):
                    if len(alias) > 1:
                        names.add(alias)
    return names


def load_food_homology(csv_path: Path, docx_path: Path) -> dict[str, dict[str, Any]]:
    mapping = {}
    with csv_path.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            herb_name = clean_text(row.get("herb_name"))
            if herb_name:
                mapping[herb_name] = row
    if mapping:
        return mapping
    for herb_name in parse_food_homology_docx(docx_path):
        mapping[herb_name] = {
            "herb_name": herb_name,
            "is_food_homology": True,
            "homology_source": "药食同源106种目录.docx",
        }
    return mapping


def build_graph(data_dir: Path, food_csv_path: Path) -> Builder:
    builder = Builder()
    food_homology = load_food_homology(food_csv_path, DEFAULT_FOOD_DOCX)

    baseline_path = data_dir / "Baseline_Top5_对比结果.xlsx"
    for row in read_sheet_rows(baseline_path):
        source = clean_text(row.get("原药材"))
        target = clean_text(row.get("替代药材"))
        if not source or not target:
            continue
        builder.baseline_by_herb[source].append(
            {
                "method": clean_text(row.get("方法")) or "Baseline",
                "rank": int(float(row.get("Rank") or 0)),
                "target_name": target,
                "score": float(row.get("相似度") or 0),
            }
        )

    standard_path = data_dir / "功效标签_标准化清洗.xlsx"
    tag_to_category: dict[str, str] = {}
    for row in read_sheet_rows(standard_path, "标准功效词典"):
        tag_name = clean_text(row.get("标准功效标签"))
        if not tag_name:
            continue
        tag_to_category[tag_name] = clean_text(row.get("上级类别")) or "未分类"
        builder.add_efficacy(
            tag_name,
            category_name=tag_to_category[tag_name],
            keywords=row.get("匹配关键词"),
            description=row.get("说明"),
        )

    for row in read_sheet_rows(standard_path, "标准化结果"):
        herb_name = clean_text(row.get("药材名"))
        if not herb_name:
            continue
        food_row = food_homology.get(herb_name, {})
        aliases = [clean_text(food_row.get("pinyin_name")), clean_text(food_row.get("latin_name"))]
        builder.add_herb(
            herb_name,
            pinyin_name=food_row.get("pinyin_name"),
            latin_name=food_row.get("latin_name"),
            taste=food_row.get("taste") or row.get("性味"),
            property=food_row.get("property") or row.get("性味"),
            meridian_tropism=food_row.get("meridian_tropism") or row.get("归经"),
            core_efficacy_tcm=food_row.get("core_efficacy_tcm") or row.get("功效"),
            core_efficacy_modern=food_row.get("core_efficacy_modern"),
            contraindications=food_row.get("contraindications") or row.get("禁忌"),
            safe_dosage_range=food_row.get("safe_dosage_range"),
            max_safe_dosage=food_row.get("max_safe_dosage"),
            homology_source=food_row.get("homology_source"),
            classic_prescription=food_row.get("classic_prescription"),
            is_food_homology=str(food_row.get("is_food_homology", "")).lower() == "true",
            standardized_efficacy_text=row.get("功效_规范化文本"),
            indications=row.get("主治"),
            aliases=[alias for alias in aliases if alias],
            sources=["功效标签_标准化清洗", "中国药典中药材数据_106种药食同源.csv"] if food_row else ["功效标签_标准化清洗"],
        )
        for tag_name in [clean_text(part) for part in str(row.get("标准功效标签") or "").split("；") if clean_text(part)]:
            tag_key = builder.add_efficacy(tag_name, category_name=tag_to_category.get(tag_name))
            builder.herb_tag_edges.add((herb_key(herb_name), tag_key))

    mol_path = data_dir / "mol_ecfp_effect.xlsx"
    for row in read_sheet_rows(mol_path):
        herb_name = clean_text(row.get("中药名"))
        if not herb_name:
            continue
        food_row = food_homology.get(herb_name, {})
        aliases = [clean_text(row.get("拼音")), clean_text(food_row.get("pinyin_name")), clean_text(food_row.get("latin_name"))]
        herb_id = builder.add_herb(
            herb_name,
            pinyin_name=row.get("拼音") or food_row.get("pinyin_name"),
            latin_name=food_row.get("latin_name"),
            taste=food_row.get("taste") or row.get("性味"),
            property=food_row.get("property") or row.get("性味"),
            meridian_tropism=food_row.get("meridian_tropism") or row.get("归经"),
            core_efficacy_tcm=food_row.get("core_efficacy_tcm") or row.get("功效"),
            core_efficacy_modern=food_row.get("core_efficacy_modern"),
            contraindications=food_row.get("contraindications"),
            safe_dosage_range=food_row.get("safe_dosage_range"),
            max_safe_dosage=food_row.get("max_safe_dosage"),
            homology_source=food_row.get("homology_source"),
            classic_prescription=food_row.get("classic_prescription"),
            is_food_homology=str(food_row.get("is_food_homology", "")).lower() == "true",
            aliases=[alias for alias in aliases if alias],
            sources=["mol_ecfp_effect", "中国药典中药材数据_106种药食同源.csv"] if food_row else ["mol_ecfp_effect"],
        )
        ingredient_id = builder.add_ingredient(row)
        if ingredient_id:
            builder.herb_ingredient_edges.add((herb_id, ingredient_id))

    gnn_path = data_dir / "GNN_Top5_替代结果.xlsx"
    for row in read_sheet_rows(gnn_path):
        source = clean_text(row.get("原药材"))
        target = clean_text(row.get("替代药材"))
        if not source or not target:
            continue
        source_key = builder.add_herb(
            source,
            is_food_homology=str(food_homology.get(source, {}).get("is_food_homology", "")).lower() == "true",
            baseline_candidates_json=json.dumps(builder.baseline_by_herb.get(source, []), ensure_ascii=False),
            sources=["GNN_Top5_替代结果"],
        )
        target_key = builder.add_herb(
            target,
            is_food_homology=str(food_homology.get(target, {}).get("is_food_homology", "")).lower() == "true",
            sources=["GNN_Top5_替代结果"],
        )
        builder.replacement_edges.append(
            ReplacementEdge(
                source_key=source_key,
                target_key=target_key,
                props={
                    "model": "GNN",
                    "rank": int(float(row.get("Rank") or 0)),
                    "score": float(row.get("相似度") or 0),
                    "source_type": "formal_gnn",
                },
            )
        )

    for herb_name, food_row in food_homology.items():
        if herb_key(herb_name) in builder.herbs:
            continue
        builder.add_herb(
            herb_name,
            pinyin_name=food_row.get("pinyin_name"),
            latin_name=food_row.get("latin_name"),
            taste=food_row.get("taste"),
            property=food_row.get("property"),
            meridian_tropism=food_row.get("meridian_tropism"),
            core_efficacy_tcm=food_row.get("core_efficacy_tcm"),
            core_efficacy_modern=food_row.get("core_efficacy_modern"),
            contraindications=food_row.get("contraindications"),
            safe_dosage_range=food_row.get("safe_dosage_range"),
            max_safe_dosage=food_row.get("max_safe_dosage"),
            homology_source=food_row.get("homology_source") or "药食同源106种目录.docx",
            classic_prescription=food_row.get("classic_prescription"),
            is_food_homology=True,
            aliases=[clean_text(food_row.get("pinyin_name")), clean_text(food_row.get("latin_name"))],
            sources=["药食同源目录补全"],
        )
    return builder


def import_to_neo4j(builder: Builder, uri: str, username: str, password: str, batch_size: int = 500) -> dict[str, int]:
    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            session.run("CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (n:Entity) REQUIRE n.key IS UNIQUE")

            def write_nodes(label: str, nodes: dict[str, NodeRecord]) -> None:
                records = [{"key": node.key, "props": compact_props(node.props)} for node in nodes.values()]
                for start in range(0, len(records), batch_size):
                    batch = records[start : start + batch_size]
                    session.run(
                        f"""
UNWIND $rows AS row
MERGE (n:Entity {{key: row.key}})
SET n:{label}
SET n += row.props
""",
                        {"rows": batch},
                    )

            write_nodes("Herb", builder.herbs)
            write_nodes("Ingredient", builder.ingredients)
            write_nodes("EfficacyTag", builder.efficacy_tags)
            write_nodes("EfficacyCategory", builder.efficacy_categories)

            def write_edges(rows: list[dict[str, Any]], rel_type: str, set_props: bool = False) -> None:
                for start in range(0, len(rows), batch_size):
                    batch = rows[start : start + batch_size]
                    query = f"""
UNWIND $rows AS row
MATCH (a:Entity {{key: row.source}})
MATCH (b:Entity {{key: row.target}})
MERGE (a)-[r:{rel_type}]->(b)
"""
                    if set_props:
                        query += "SET r += row.props\n"
                    session.run(query, {"rows": batch})

            write_edges([{"source": source, "target": target} for source, target in builder.herb_ingredient_edges], "HAS_INGREDIENT")
            write_edges([{"source": source, "target": target} for source, target in builder.herb_tag_edges], "HAS_EFFICACY_TAG")
            write_edges([{"source": source, "target": target} for source, target in builder.tag_category_edges], "BELONGS_TO_CATEGORY")
            write_edges(
                [{"source": edge.source_key, "target": edge.target_key, "props": edge.props} for edge in builder.replacement_edges],
                "CAN_REPLACE",
                set_props=True,
            )
        return {
            "herbs": len(builder.herbs),
            "ingredients": len(builder.ingredients),
            "efficacy_tags": len(builder.efficacy_tags),
            "efficacy_categories": len(builder.efficacy_categories),
            "herb_ingredient_edges": len(builder.herb_ingredient_edges),
            "herb_tag_edges": len(builder.herb_tag_edges),
            "replacement_edges": len(builder.replacement_edges),
        }
    finally:
        driver.close()


def validate(builder: Builder) -> dict[str, Any]:
    missing_replacement_targets = [
        edge.target_key for edge in builder.replacement_edges if edge.target_key not in builder.herbs
    ]
    food_marked = sum(1 for node in builder.herbs.values() if node.props.get("is_food_homology"))
    return {
        "duplicate_herb_keys": len(builder.herbs) - len({node.key for node in builder.herbs.values()}),
        "missing_replacement_targets": len(missing_replacement_targets),
        "food_homology_marked": food_marked,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import formal herbal R&D knowledge graph into Neo4j.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--food-csv", type=Path, default=DEFAULT_FOOD_CSV)
    parser.add_argument("--neo4j-uri", default="neo4j://localhost:7687")
    parser.add_argument("--neo4j-username", default="neo4j")
    parser.add_argument("--neo4j-password", default="3217858658")
    args = parser.parse_args()

    builder = build_graph(args.data_dir, args.food_csv)
    validation = validate(builder)
    stats = import_to_neo4j(builder, args.neo4j_uri, args.neo4j_username, args.neo4j_password)
    print(json.dumps({"validation": validation, "stats": stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
