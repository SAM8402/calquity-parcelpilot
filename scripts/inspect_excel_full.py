import pandas as pd
from pathlib import Path

xlsx = Path(__file__).resolve().parents[1] / "backend/data/excel/ParcelPilot_Assessment_Data.xlsx"
for s in ["tickets", "orders", "accounts"]:
    df = pd.read_excel(xlsx, sheet_name=s)
    print("=" * 60, s)
    print("columns:", list(df.columns))
    print("dtypes:\n", df.dtypes)
    print(df.to_string(index=False)[:2500])
    print()
