"""Push a downloaded Meeting Report .xlsx into the destination Google Sheet's
'Raw MT Data' tab: clear it, then paste the report 1:1 as plain values (no
formulas, no formatting carried over — the Sheets API only ever writes cell
values, so "paste as values" is the only thing `update()` can do).

    .venv/bin/python push_to_sheet.py downloads/meeting_report_....xlsx
"""
import sys

import gspread
import openpyxl

import config


def read_xlsx_values(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append(["" if v is None else (v.isoformat(sep=" ") if hasattr(v, "isoformat") else v) for v in row])
    return rows


def push(xlsx_path):
    values = read_xlsx_values(xlsx_path)
    gc = gspread.service_account(filename=str(config.SA_CREDS))
    ws = gc.open_by_url(config.SHEET_URL).worksheet(config.SHEET_TAB)
    ws.clear()
    ws.update(values, value_input_option="RAW")
    print(f"Pasted {len(values)} rows x {len(values[0]) if values else 0} cols into '{config.SHEET_TAB}'")


if __name__ == "__main__":
    push(sys.argv[1])
