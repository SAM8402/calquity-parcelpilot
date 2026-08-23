from pathlib import Path

import pandas as pd
import duckdb
from app.config import EXCEL_DIR, DB_PATH


def ingest_excel_to_db(excel_path: str = None, db_path: str = None):
    excel_file = Path(excel_path) if excel_path else None
    db_file = Path(db_path) if db_path else DB_PATH

    if excel_file is None:
        xlsx_files = list(EXCEL_DIR.glob("*.xlsx"))
        if not xlsx_files:
            print(f"No Excel files found in {EXCEL_DIR}")
            return None
        excel_file = xlsx_files[0]

    if not excel_file.exists():
        print(f"Excel file not found: {excel_file}")
        return None

    xls = pd.ExcelFile(excel_file)
    con = duckdb.connect(str(db_file))

    for sheet_name in xls.sheet_names:
        if sheet_name.upper() == "README":
            readme_df = pd.read_excel(xls, sheet_name=sheet_name)
            print(f"README sheet snapshot info:")
            print(readme_df.to_string(index=False))
            continue

        df = pd.read_excel(xls, sheet_name=sheet_name)
        table_name = sheet_name.lower().replace(" ", "_").replace("-", "_")
        con.execute(f"DROP TABLE IF EXISTS {table_name}")
        con.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
        print(f"Loaded {len(df)} rows into table: {table_name}")

    con.close()
    print(f"Database created at: {db_file}")
    return db_file


if __name__ == "__main__":
    ingest_excel_to_db()
