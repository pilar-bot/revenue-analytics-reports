import pandas as pd
import io
from config import COLUMN_MAP, COLUMN_MAP_EXCEL


def load_file(uploaded_file) -> pd.DataFrame:
    """
    Accept a Streamlit UploadedFile (CSV or Excel) and return a raw DataFrame
    with internal column names as defined in COLUMN_MAP / COLUMN_MAP_EXCEL.
    Raises ValueError with a user-friendly message if required columns are missing.
    """
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        # RoomMaster exports are often Windows-1252; fall back through common encodings
        for enc in ("utf-8-sig", "windows-1252", "latin-1"):
            try:
                if hasattr(uploaded_file, "seek"):
                    uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, dtype=str, encoding=enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            raise ValueError("Could not decode the CSV file. Try saving it as UTF-8 from Excel.")
        col_map = COLUMN_MAP
    elif name.endswith((".xlsx", ".xls")):
        xf = pd.ExcelFile(uploaded_file)
        sheet = "Raw Data" if "Raw Data" in xf.sheet_names else xf.sheet_names[0]
        raw = pd.read_excel(xf, sheet_name=sheet, header=None, dtype=str)
        header_row = _find_header_row(raw, "Conf #")
        df = pd.read_excel(xf, sheet_name=sheet, header=header_row, dtype=str)
        col_map = COLUMN_MAP_EXCEL
    else:
        raise ValueError("Unsupported file type. Upload a .csv or .xlsx file.")

    df = df.dropna(how="all").reset_index(drop=True)
    return _rename_columns(df, col_map)


def _find_header_row(df: pd.DataFrame, marker: str) -> int:
    for i, row in df.iterrows():
        if any(str(v).strip() == marker for v in row.values):
            return i
    return 0


def _rename_columns(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """
    Rename file columns to internal names using the provided column map.
    Missing optional columns are added as empty strings.
    Required columns that are absent raise ValueError.
    """
    required = {"conf_num", "room_type", "nights", "checkin", "cancel_date", "rate_code"}
    optional = {"name", "cancelled_by"}

    reverse = {v: k for k, v in col_map.items()}
    df = df.rename(columns=lambda c: reverse.get(str(c).strip(), str(c).strip()))

    missing_required = required - set(df.columns)
    if missing_required:
        expected = [col_map[k] for k in missing_required]
        raise ValueError(
            f"Required columns not found in file: {', '.join(expected)}\n"
            f"Check your file headers and update COLUMN_MAP in config.py if needed."
        )

    for col in optional:
        if col not in df.columns:
            df[col] = ""

    return df
