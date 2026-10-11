# -*- coding: utf-8 -*-
"""纯标准库 xlsx 读取器（zipfile + ElementTree），不依赖 openpyxl/pandas。

从 `scripts/import_neo4j_kg.py` 抽离而来（2026-10-12，管理端导入功能 A 阶段），
该脚本现在改为从这里导入，保持单一实现。仅支持 .xlsx；整表载入内存，
调用方需自行限制文件体积与行数。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any, Iterator
import xml.etree.ElementTree as ET


NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
DEFAULT_DATA_DIR = Path(r"D:\工作\多智能体-宋\替代映射库-建模")
DEFAULT_FOOD_CSV = Path(r"D:\python_workspace\neo4j_muti_agents\origin_data\data_2\数据库\药食同源\中国药典中药材数据_106种药食同源.csv")
DEFAULT_FOOD_DOCX = Path(r"D:\python_workspace\neo4j_muti_agents\origin_data\data_2\数据库\经典名方\药食同源106种目录.docx")




def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("\u0000", "")
    return text or None



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


