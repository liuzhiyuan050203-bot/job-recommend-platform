"""把职位的职责、任职要求、福利整理成知识库用的干净正文。

校招官网 / 飞书 ATS 导入的职位在 requirement 里存抓取元数据 JSON（{"provenance": {...}}），
description 前几行是【来源】【抓取时间】等，welfare 常是投递链接。这些保留在数据库供溯源，
展示侧已由后端 JobTextCleaner 拆出；这里用同一套规则生成知识库文本，避免 JSON 污染检索。
不改库里的原始字段。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

ESTIMATE_MARK = "薪资为平台按方向与城市估算"

_META_LINE = re.compile(r"^【(校招官网投递|来源|项目/方向|工作城市|抓取时间)】\s*(.*)$")
_NAME_LINE = re.compile(r"^岗位名称[:：]")
_SYNC_LINE = re.compile(r"^本条记录由.*同步")
_APPLY_LINE = re.compile(r"^投递链接[:：]\s*(\S+)\s*$")
_BULLET = re.compile(
    r"^\s*(?:[（(]?\d{1,2}[)）.、．:：](?!\d)|[•·\-*●▪]|[一二三四五六七八九十][、.])\s*"
)
_URL = re.compile(r"https?://\S+")
_LIST_KEYS = ("requirements", "requirement", "duties", "items", "content", "text", "list")
_ITEM_KEYS = ("text", "content", "name", "value", "desc")
_SOURCE_LABELS = {
    "platform": "企业发布",
    "self_crawl": "校招官网同步（外部来源）",
    "ext_ats": "飞书招聘公开门户（外部扩充库）",
}
_EDU_LABEL = {0: "学历不限", 1: "专科", 2: "本科", 3: "硕士", 4: "博士"}
_EXP_LABEL = {0: "经验不限", 1: "应届生", 2: "一年以内", 3: "一到三年", 4: "三到五年", 5: "五年以上"}


@dataclass
class CleanedJobText:
    description: str = ""
    requirement: str = ""
    welfare: str = ""
    data_source: str = "platform"
    source_label: str = "企业发布"
    source_site: str = ""
    source_company: str = ""
    apply_url: str = ""
    project: str = ""
    work_cities: str = ""
    salary_estimated: bool = False
    extra: dict = field(default_factory=dict)


def looks_like_json(text: str) -> bool:
    text = (text or "").strip()
    return text.startswith("{") or text.startswith("[") or (text.startswith('"') and text.endswith('"'))


def clean_job_fields(
    description: str | None,
    requirement: str | None,
    welfare: str | None,
    data_source: str | None = "platform",
) -> CleanedJobText:
    """从原始库字段抽出给人看的正文，元数据进 CleanedJobText 的来源字段。"""
    source = CleanedJobText(data_source=(data_source or "platform").strip() or "platform")
    req = (requirement or "").strip()
    req_items: list[str] = []
    if looks_like_json(req):
        node = _parse_json(req)
        if node is not None:
            source.salary_estimated = _read_provenance(node, source) or source.salary_estimated
            req_items.extend(_items_of(node))
        else:
            req_items.extend(_split_text(_strip_json_punctuation(req)))
    elif req:
        req_items.extend(_split_text(req))

    desc_items: list[str] = []
    for line in _lines(description):
        matched = _META_LINE.match(line)
        if matched:
            _fill_from_meta(source, matched.group(1), matched.group(2).strip())
            continue
        if _NAME_LINE.search(line):
            continue
        if _SYNC_LINE.search(line) or ESTIMATE_MARK in line:
            source.salary_estimated = source.salary_estimated or ESTIMATE_MARK in line
            if not source.source_site and not source.source_company:
                source.extra.setdefault("crawler", True)
            continue
        item = _strip_bullet(line)
        if item:
            desc_items.append(item)

    welfare_parts: list[str] = []
    for line in _lines(welfare):
        apply = _APPLY_LINE.match(line)
        if apply:
            if not source.apply_url:
                source.apply_url = apply.group(1)
            continue
        welfare_parts.append(line)

    source.description = "；".join(desc_items)
    source.requirement = "；".join(req_items)
    source.welfare = "\n".join(welfare_parts).strip()
    _finalize_source(source)
    if source.data_source in {"self_crawl", "ext_ats"}:
        source.salary_estimated = True
    return source


def build_job_text(row: dict) -> str:
    """统一职位知识库文本模板：标题、公司、城市、薪资、技能、要求、职责。"""
    cleaned = clean_job_fields(
        row.get("description"),
        row.get("requirement"),
        row.get("welfare"),
        row.get("data_source") or "platform",
    )
    salary = f"{int(row['salary_min'] or 0)}-{int(row['salary_max'] or 0)}元/月"
    months = int(row.get("salary_months") or 12)
    if months != 12:
        salary += f"，{months}薪"
    if cleaned.salary_estimated:
        salary += "（估算，以官网为准）"
    lines = [
        f"# {row['title']}",
        f"公司：{row.get('company_name') or ''}",
        f"城市：{row.get('city') or ''}",
        f"方向：{row.get('tech_direction') or ''}",
        f"薪资：{salary}",
        f"学历：{_EDU_LABEL.get(int(row.get('education') or 0), '不限')}",
        f"经验：{_EXP_LABEL.get(int(row.get('experience_req') or 0), '不限')}",
        f"技能：{row.get('skills') or '未标注'}",
        f"来源：{_source_line(cleaned)}",
    ]
    if cleaned.description:
        lines.append("职责：" + cleaned.description[:800])
    if cleaned.requirement:
        lines.append("要求：" + cleaned.requirement[:800])
    if cleaned.welfare:
        lines.append("福利：" + cleaned.welfare.strip()[:200])
    return "\n".join(lines)


def job_meta(row: dict, cleaned: CleanedJobText | None = None) -> dict:
    if cleaned is None:
        cleaned = clean_job_fields(
            row.get("description"),
            row.get("requirement"),
            row.get("welfare"),
            row.get("data_source") or "platform",
        )
    return {
        "data_source": cleaned.data_source,
        "company": str(row.get("company_name") or "")[:200],
        "city": str(row.get("city") or "")[:64],
        "salary_estimated": bool(cleaned.salary_estimated),
        "source_label": cleaned.source_label[:120],
    }


def _source_line(cleaned: CleanedJobText) -> str:
    label = cleaned.source_label or _SOURCE_LABELS.get(cleaned.data_source, "未知来源")
    parts = [label]
    if cleaned.source_company and cleaned.source_company not in label:
        parts.append(cleaned.source_company)
    elif cleaned.source_site and cleaned.source_site not in label:
        parts.append(cleaned.source_site)
    if cleaned.salary_estimated and "估算" not in "".join(parts):
        parts.append("薪资为估算")
    return "，".join(parts)


def _finalize_source(source: CleanedJobText) -> None:
    if source.data_source == "ext_ats":
        source.source_label = _SOURCE_LABELS["ext_ats"]
    elif source.data_source == "self_crawl" or source.source_site or source.source_company or source.extra.get("crawler"):
        if source.data_source == "platform":
            source.data_source = "self_crawl"
        source.source_label = _SOURCE_LABELS.get(source.data_source, _SOURCE_LABELS["self_crawl"])
        if source.source_company:
            source.source_label = f"{source.source_label} / {source.source_company}"
    else:
        source.source_label = _SOURCE_LABELS.get(source.data_source, "企业发布")


def _parse_json(text: str):
    try:
        node = json.loads(text)
        if isinstance(node, str) and looks_like_json(node.strip()):
            inner = _parse_json(node.strip())
            return node if inner is None else inner
        return node
    except Exception:
        return None


def _read_provenance(node, source: CleanedJobText) -> bool:
    if not isinstance(node, dict):
        return _flag(node)
    raw = node.get("provenance") if isinstance(node.get("provenance"), dict) else node
    site = _text(raw, "source", "crawl_source", "platform")
    company = _text(raw, "company_label", "company")
    if not site and not company and "apply_url" not in raw:
        return _flag(node)
    source.source_site = site or source.source_site
    source.source_company = company or source.source_company
    source.apply_url = _text(raw, "apply_url", "url") or source.apply_url
    source.project = _text(raw, "project") or source.project
    source.work_cities = _text(raw, "work_cities") or source.work_cities
    ds = _text(raw, "data_source")
    if ds in _SOURCE_LABELS:
        source.data_source = ds
    return _flag(node) or _flag(raw)


def _flag(node) -> bool:
    if not isinstance(node, dict):
        return False
    for key in ("salary_estimated", "is_estimated_salary", "is_estimated"):
        value = node.get(key)
        if value is True or (isinstance(value, str) and value.lower() in {"true", "1", "yes"}):
            return True
    return False


def _items_of(node) -> list[str]:
    out: list[str] = []
    if isinstance(node, list):
        for item in node:
            if isinstance(item, (str, int, float)):
                out.extend(_split_text(str(item)))
            elif isinstance(item, dict):
                text = _text(item, *_ITEM_KEYS)
                if text:
                    out.extend(_split_text(text))
    elif isinstance(node, dict):
        for key in _LIST_KEYS:
            if key in node:
                out.extend(_items_of(node[key]))
                if out:
                    break
    elif isinstance(node, str):
        out.extend(_split_text(node))
    return out


def _text(node, *keys: str) -> str:
    if not isinstance(node, dict):
        return ""
    for key in keys:
        value = node.get(key)
        if value is not None and not isinstance(value, (dict, list)):
            text = str(value).strip()
            if text:
                return text
    return ""


def _fill_from_meta(source: CleanedJobText, key: str, value: str) -> None:
    source.extra["crawler"] = True
    if key == "校招官网投递":
        found = _URL.search(value)
        if found and not source.apply_url:
            source.apply_url = found.group(0)
    elif key == "来源":
        parts = re.split(r"\s*/\s*", value)
        if parts and not source.source_site:
            source.source_site = parts[0]
        if len(parts) > 1 and not source.source_company:
            source.source_company = parts[1]
    elif key == "项目/方向" and not source.project:
        source.project = re.split(r"\s*/\s*", value)[0]
    elif key == "工作城市" and not source.work_cities:
        source.work_cities = value
    elif key == "抓取时间":
        source.extra["crawled_at"] = value


def _split_text(text: str) -> list[str]:
    out: list[str] = []
    for line in _lines(text):
        for piece in re.split(r"[；;]", line):
            item = _strip_bullet(piece)
            if item:
                out.append(item)
    return out


def _lines(text: str | None) -> list[str]:
    if not text:
        return []
    normalized = (
        str(text).replace("\\r\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n")
    )
    return [line.strip() for line in normalized.split("\n") if line.strip()]


def _strip_bullet(text: str) -> str:
    item = (text or "").strip()
    matched = _BULLET.match(item)
    if matched:
        item = item[matched.end() :]
    return re.sub(r"[。；;，,\s]+$", "", item).strip()


def _strip_json_punctuation(text: str) -> str:
    cleaned = re.sub(r'^[\[{\s"]+|[\]}\s"]+$', "", text)
    cleaned = cleaned.replace('\\"', '"')
    cleaned = re.sub(r'"\s*,\s*"', "\n", cleaned)
    return cleaned
