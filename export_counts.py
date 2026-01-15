# This code reads the SQlite database and creates a summary CSV which shows the number of entries in each error category. 
import sqlite3
import csv
db = r"C:\projectSandpit\csd_results_complete.sqlite"

con = sqlite3.connect(db)
cur = con.cursor()
cur.execute("SELECT category, COUNT(*) AS n FROM results GROUP BY category ORDER BY n DESC")
rows = cur.fetchall()
con.close()

with open("counts_summary.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["category", "count"])
    w.writerows(rows)

print("Wrote counts_summary.csv (rows: {})".format(len(rows)))

# This code reads the SQLite database and creates a text file containing the identifiers of all entries in the empty_smiles error categroy. 
DB_PATH = r"C:\projectSandpit\csd_results_complete.sqlite"
OUT_TXT = "empty_smiles_identifiers.txt"
CATEGORY = "empty_smiles" 

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

cur.execute("""
    SELECT identifier
    FROM results
    WHERE category = ?
""", (CATEGORY,))

written = 0
with open(OUT_TXT, "w", encoding="utf-8") as fh:
    for (identifier,) in cur:
        if identifier:
            fh.write(identifier.strip() + "\n")
            written += 1

con.close()

print(f"Wrote {written} identifiers to {OUT_TXT}")
