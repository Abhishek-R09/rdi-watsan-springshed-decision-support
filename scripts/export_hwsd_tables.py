"""Export the HWSD v2.0 Access tables used by build_spring_features.py to CSV.

Usage: python scripts/export_hwsd_tables.py <cache>/hwsd/HWSD2.mdb
Needs the pure-Python `access_parser` package (pip install access-parser).
"""

import csv
import sys
from pathlib import Path

from access_parser import AccessParser

TABLES = ["HWSD2_SMU", "HWSD2_LAYERS", "D_WRB4", "D_DRAINAGE", "D_TEXTURE_USDA"]


def main():
    mdb = Path(sys.argv[1])
    database = AccessParser(str(mdb))
    for name in TABLES:
        table = database.parse_table(name)
        keys = list(table.keys())
        with (mdb.parent / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(keys)
            for index in range(len(table[keys[0]])):
                writer.writerow([table[key][index] for key in keys])
        print(name, len(table[keys[0]]))


if __name__ == "__main__":
    main()
