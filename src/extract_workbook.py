"""Optional: reproduce source CSVs from the supplied XLSB or a local XLSX copy.

Requires pandas + pyxlsb for XLSB; openpyxl for XLSX. The core pipeline uses
only Python's standard library and runs from the included source CSVs.
"""
import argparse
import csv
from pathlib import Path

def extract(path, output):
    output.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == '.xlsb':
        import pandas as pd
        book = pd.ExcelFile(path, engine='pyxlsb')
        sheets = ((name, pd.read_excel(book, sheet_name=name, dtype=object)) for name in book.sheet_names)
        for name, frame in sheets:
            frame.to_csv(output / f'{name}.csv', index=False, lineterminator='\n')
    elif path.suffix.lower() == '.xlsx':
        import openpyxl
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for sheet in book:
            rows=list(sheet.values)
            with (output / f'{sheet.title}.csv').open('w', newline='', encoding='utf-8') as f:
                csv.writer(f, lineterminator='\n').writerows(rows)
            with (output / f'{sheet.title}.csv').open(newline='',encoding='utf-8') as f:
                extracted=list(csv.reader(f))
            if len(extracted)!=len(rows):
                raise ValueError(f'{sheet.title}: extraction row count changed')
            print(f'{sheet.title}: {len(rows)-1} rows extracted and checked')
    else:
        raise ValueError('Use the XLSB source or an XLSX conversion.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    parser.add_argument('--out', type=Path, default=Path('data/source'))
    args = parser.parse_args()
    extract(args.workbook, args.out)
