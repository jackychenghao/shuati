import re
from datetime import datetime, timedelta


def normalize_datetime_text(raw: str, subject: str = "") -> str:
    s = (raw or "").strip()
    now = datetime.now()

    if not s and subject:
        m = re.search(r"(\d{4})(\d{2})(\d{2})", subject)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)} 00:00:00"
        return ""

    m = re.match(r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?\s*$", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh = int(m.group(4) or 0)
        mm = int(m.group(5) or 0)
        ss = int(m.group(6) or 0)
        try:
            return datetime(y, mo, d, hh, mm, ss).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    m = re.match(r"^\s*(\d{1,2})[./-](\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?\s*$", s)
    if m:
        mo, d = int(m.group(1)), int(m.group(2))
        hh, mm = int(m.group(3)), int(m.group(4))
        ss = int(m.group(5) or 0)
        y = now.year
        try:
            dt = datetime(y, mo, d, hh, mm, ss)
            if dt > now + timedelta(days=7):
                dt = datetime(y - 1, mo, d, hh, mm, ss)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    m = re.match(r"^\s*(\d+)\s*天(?:前|之前)\s*(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?\s*$", s)
    if m:
        days = int(m.group(1))
        hh, mm = int(m.group(2)), int(m.group(3))
        ss = int(m.group(4) or 0)
        dt = now - timedelta(days=days)
        dt = dt.replace(hour=hh, minute=mm, second=ss, microsecond=0)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    m = re.match(r"^\s*(昨天|前天|今天)\s*(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?\s*$", s)
    if m:
        word = m.group(1)
        hh, mm = int(m.group(2)), int(m.group(3))
        ss = int(m.group(4) or 0)
        delta = 0 if word == "今天" else 1 if word == "昨天" else 2
        dt = now - timedelta(days=delta)
        dt = dt.replace(hour=hh, minute=mm, second=ss, microsecond=0)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    if subject:
        m = re.search(r"(\d{4})(\d{2})(\d{2})", subject)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)} 00:00:00"

    return s
