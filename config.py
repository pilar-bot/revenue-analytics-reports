CHANNEL_MAP = {
    "EX": "Expedia",
    "HB": "Hotels.com",
    "HI": "Hotels.com",
    "HP": "Hotels.com",
    "HT": "Hotels.com",
    "AG": "Agoda",
    "BK": "Booking.com",
    "BO": "Booking.com",
    "AT": "Airbnb/Travelport",
    "D":  "Property Direct",   # single-letter prefix — catches any D* code
    "NW": "Wholesale/FIT",
    "TF": "Wholesale/FIT",
    "WB": "Wholesale/FIT",
    "IH": "IHG / Synxis",
}

CHANNEL_ORDER = [
    "Expedia",
    "Hotels.com",
    "No Rate Code",
    "Agoda",
    "Booking.com",
    "Property Direct",
    "Wholesale/FIT",
    "Airbnb/Travelport",
    "IHG / Synxis",
]

LEAD_TIME_BUCKETS = [
    (0,   0,    "0 — Same Day"),
    (1,   7,    "1–7 days"),
    (8,   14,   "8–14 days"),
    (15,  30,   "15–30 days"),
    (31,  60,   "31–60 days"),
    (61,  90,   "61–90 days"),
    (91,  180,  "91–180 days"),
    (181, 9999, "180+ days"),
]

BUCKET_ORDER = [b[2] for b in LEAD_TIME_BUCKETS]

BUCKET_SIGNALS = {
    "0 — Same Day": "⚠️ Last-Minute Risk",
    "1–7 days":     "⚠️ Last-Minute Risk",
    "8–14 days":    "Standard",
    "15–30 days":   "Standard",
    "31–60 days":   "🎯 Peak Window",
    "61–90 days":   "Standard",
    "91–180 days":  "📅 Advanced Planner",
    "180+ days":    "📅 Advanced Planner",
}

# Rate code prefixes to exclude (BAR rate codes)
BAR_PREFIXES = ["BAR"]

# Room type code → display name mapping
ROOM_TYPE_NAMES = {
    "STK":  "Studio (King)",
    "STPC": "Studio (Pool/City View)",
    "STPO": "Studio (Pool/Ocean View)",
    "1BS":  "1BR Suite",
    "1BPO": "1BR Pool/Ocean",
    "HSP":  "Hotel Suite Premium",
    "1BPC": "1BR Pool/City",
    "HSP1": "Hotel Suite Prem 1",
    "STKH": "Studio King High Floor",
}

OTA_CHANNELS = {"Expedia", "Hotels.com", "Agoda", "Booking.com", "Airbnb/Travelport"}

# RoomMaster CSV column name mapping (raw export format)
# Keys are internal names; values are the actual column headers in the RoomMaster CSV.
# NOTE: RoomMaster's CSV export has the column labels swapped — "Cancelled By" contains
# the cancel date and "Cancel Date" contains the who-cancelled code.
COLUMN_MAP = {
    "conf_num":    "Conf #",
    "name":        "Name",
    "room_type":   "Type",
    "nights":      "Ngt",
    "checkin":     "CheckIn",
    "cancel_date": "Cancelled By",
    "rate_code":   "Rate Code",
    "cancelled_by":"Cancel Date",
}

# Excel (revenue manager format) uses different column headers for the same fields
COLUMN_MAP_EXCEL = {
    "conf_num":    "Conf #",
    "name":        "Name",
    "room_type":   "Room Type",
    "nights":      "Nights",
    "checkin":     "Check-In",
    "cancel_date": "Cancel Date",
    "rate_code":   "Rate Code",
    "cancelled_by":"Cancelled By",
}
