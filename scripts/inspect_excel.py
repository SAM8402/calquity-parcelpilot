import pandas as pd
from pathlib import Path

xlsx = Path(__file__).resolve().parents[1] / "backend/data/excel/ParcelPilot_Assessment_Data.xlsx"
xls = pd.ExcelFile(xlsx)
print("sheets:", xls.sheet_names)
for s in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name=s)
    print(f"\n=== {s} ({len(df)} rows) cols={list(df.columns)} ===")
    print(df.head(5).to_string(index=False)[:1200])
