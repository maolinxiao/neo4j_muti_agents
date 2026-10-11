# -*- coding: utf-8 -*-
"""生成管理端「数据导入」的 Excel 模板（开发期脚本，2026-10-12）。

- 依赖 openpyxl，**仅开发/生成时使用**，服务端不需要（线上解析用纯标准库读取器）。
- 每个模板两个工作表：
    <规范工作表名>  仅表头（列名与 kg_import_core 的解析器逐字一致），供填写
    填写说明        必填列、列含义、示例行（示例只写在这里，避免被误导入）
- 用法：python scripts/build_import_templates.py（在后端 PYTHONPATH 下运行）

改列名/新增数据类型时：改 backend/app/services/kg_import_service.py 的 IMPORT_TYPES，
再重跑本脚本即可。
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402

from app.services.kg_import_service import (  # noqa: E402
    IMPORT_TYPES,
    KB4_CO_SHEETS,
    template_dir,
    template_path,
)


def build_one(import_type) -> tuple[Path, int]:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = import_type.sheet
    for index, column in enumerate(import_type.columns, start=1):
        cell = sheet.cell(row=1, column=index, value=column)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2F855A" if column in import_type.required else "4A5568")
        sheet.column_dimensions[cell.column_letter].width = max(12, min(28, len(str(column)) * 2 + 4))

    # 同一文件里 builder 还会读的兄弟工作表：必须存在但保持空表（否则解析器会报「工作表缺失」）
    for co_name in import_type.co_sheets:
        co = workbook.create_sheet(co_name)
        for index, column in enumerate(KB4_CO_SHEETS.get(co_name, []), start=1):
            cell = co.cell(row=1, column=index, value=column)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="718096")
            co.column_dimensions[cell.column_letter].width = max(12, min(28, len(str(column)) * 2 + 4))

    guide = workbook.create_sheet("填写说明")
    guide.column_dimensions["A"].width = 22
    guide.column_dimensions["B"].width = 10
    guide.column_dimensions["C"].width = 60
    rows = [
        ("数据类型", import_type.name, import_type.note),
        ("工作表名", import_type.sheet, "请勿重命名工作表，否则无法解析"),
        ("", "", ""),
        ("列名", "是否必填", "说明"),
    ]
    for column in import_type.columns:
        rows.append((column, "必填" if column in import_type.required else "可选", ""))
    for row_index, row in enumerate(rows, start=1):
        for column_index, value in enumerate(row, start=1):
            cell = guide.cell(row=row_index, column=column_index, value=value)
            cell.alignment = Alignment(vertical="top", wrap_text=(column_index == 3))
            if row_index in (1, 4):
                cell.font = Font(bold=True)

    path = template_path(import_type)
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path, len(import_type.columns)


def main() -> None:
    out = template_dir()
    print(f"模板目录: {out}")
    total = 0
    for import_type in IMPORT_TYPES.values():
        path, column_count = build_one(import_type)
        total += 1
        print(f"  [{import_type.category}] {import_type.name:<18} -> {path.name}  列数={column_count}")
    print(f"共生成 {total} 个模板")


if __name__ == "__main__":
    main()
