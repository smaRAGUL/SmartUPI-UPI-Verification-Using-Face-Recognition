import sqlite3
import csv
from pathlib import Path

project_root = Path(__file__).parent
db_path = project_root / 'instance' / 'smartupi.db'

if not db_path.exists():
    raise FileNotFoundError(f'Database file not found: {db_path}')

conn = sqlite3.connect(db_path)
cur = conn.cursor()

for table, csv_file in [('user', 'registered_users.csv'), ('transaction', 'transactions.csv')]:
    cur.execute(f'SELECT * FROM "{table}"')
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    out_path = project_root / csv_file
    with out_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)
    print(f'Exported {len(rows)} rows to {out_path}')

conn.close()
