"""原始招聘 CSV 的字段解析。供 Spark 清洗任务调用。"""

from __future__ import annotations

import re
from datetime import datetime

from app.spark.dicts import CITY_PROVINCE, DIRECTION_ALIAS, EDU_TEXT, EXP_TEXT

_CITY_NAMES = sorted(CITY_PROVINCE, key=len, reverse=True)
_SALARY_PATTERNS = (
    (re.compile(r"(\d+(?:\.\d+)?)\s*[-~—至到]\s*(\d+(?:\.\d+)?)\s*万\s*/\s*年"), "year_wan"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*[-~—至到]\s*(\d+(?:\.\d+)?)\s*万\s*/\s*月"), "month_wan"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*[-~—至到]\s*(\d+(?:\.\d+)?)\s*元\s*/\s*天"), "day"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*[-~—至到]\s*(\d+(?:\.\d+)?)\s*元\s*/\s*月"), "month_yuan"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*[-~—至到]\s*(\d+(?:\.\d+)?)\s*[Kk]"), "k"),
)
_MONTHS_MARK = re.compile(r"[·•･](\d{1,2})\s*薪")


def normalize_city(text: str | None) -> str | None:
    if text is None:
        return None
    raw = str(text).strip()
    if not raw or raw.upper() in {"N/A", "NA", "NULL"}:
        return None
    if any(mark in raw for mark in ("/", "\\", "或", "、")):
        return None
    compact = re.sub(r"\s+", "", raw)
    if compact in {"火星市", "远程", "未知", "远程未知"}:
        return None
    for city in _CITY_NAMES:
        if city in compact or city in compact.replace("市", ""):
            return city
    return None


def parse_salary(text: str | None) -> tuple[str, float | None, float | None, int | None]:
    """返回 (negotiable|anomaly|ok, min, max, salary_months)。"""
    if text is None:
        return "negotiable", None, None, None
    raw = str(text).strip()
    if not raw or "面议" in raw:
        return "negotiable", None, None, None
    if raw.startswith("-"):
        return "anomaly", None, None, None
    months = 12
    marked = _MONTHS_MARK.search(raw)
    body = raw
    if marked:
        months = int(marked.group(1))
        body = raw[: marked.start()] + raw[marked.end() :]
    for pattern, kind in _SALARY_PATTERNS:
        found = pattern.search(body)
        if not found:
            continue
        low = float(found.group(1))
        high = float(found.group(2))
        if kind == "year_wan":
            low, high = low * 10000 / 12.0, high * 10000 / 12.0
        elif kind == "month_wan":
            low, high = low * 10000.0, high * 10000.0
        elif kind == "day":
            low, high = low * 21.75, high * 21.75
        elif kind == "k":
            low, high = low * 1000.0, high * 1000.0
        if low > high or low < 1000 or high > 200000:
            return "anomaly", low, high, months
        return "ok", low, high, months
    return "negotiable", None, None, None


def _map_code(text: str | None, table: dict[str, int]) -> tuple[str, int | None]:
    """empty 允许为空；unknown 表示有文本但无法映射；ok 为字典码。"""
    if text is None or not str(text).strip():
        return "empty", None
    value = table.get(str(text).strip())
    if value is None:
        return "unknown", None
    return "ok", value


def parse_date(text: str | None):
    if text is None:
        return None
    raw = str(text).strip()
    if not raw or raw in {"昨天", "0000-00-00", "null", "NULL"}:
        return None
    matched = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
    if matched:
        return _ymd(int(matched.group(1)), int(matched.group(2)), int(matched.group(3)))
    matched = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", raw)
    if matched:
        return _ymd(int(matched.group(1)), int(matched.group(2)), int(matched.group(3)))
    matched = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", raw)
    if matched:
        return _ymd(int(matched.group(1)), int(matched.group(2)), int(matched.group(3)))
    matched = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if matched:
        return _ymd(int(matched.group(3)), int(matched.group(1)), int(matched.group(2)))
    return None


def _ymd(year: int, month: int, day: int):
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def canonicalize_direction(text: str | None) -> str | None:
    if text is None or not str(text).strip():
        return None
    raw = str(text).strip()
    return DIRECTION_ALIAS.get(raw, raw)


def classify_job(salary_text, city_text, education_text, experience_text, publish_date, direction) -> dict:
    """把一行原始字段分成 negotiable、anomaly 或 valid。"""
    kind, low, high, months = parse_salary(salary_text)
    if kind == "negotiable":
        return {"status": "negotiable"}
    if kind == "anomaly":
        return {"status": "anomaly"}
    city = normalize_city(city_text)
    if not city:
        return {"status": "anomaly"}
    edu_flag, education = _map_code(education_text, EDU_TEXT)
    exp_flag, experience = _map_code(experience_text, EXP_TEXT)
    if edu_flag == "unknown" or exp_flag == "unknown":
        return {"status": "anomaly"}
    published = parse_date(publish_date)
    if published is None:
        return {"status": "anomaly"}
    average = round((low + high) / 2.0, 2)
    return {
        "status": "valid",
        "city": city,
        "province": CITY_PROVINCE[city],
        "salary_min": round(low, 2),
        "salary_max": round(high, 2),
        "salary_avg": average,
        "salary_months": int(months or 12),
        "education": education,
        "experience_req": experience,
        "publish_date": published,
        "direction": canonicalize_direction(direction),
    }
