"""确定性意图路由。

本地小模型的工具调用不稳定，因此在 LLM_TOOL_CALLING=auto 且指向本机或小参数量模型时，
由关键词和槽位决定调用哪个工具。模型返回的参数不会覆盖用户身份。
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

from app.spark.db import connect
from app.spark.dicts import CITY_PROVINCE, DIRECTION_ALIAS, EDU_TEXT

_lock = threading.Lock()
_lexicon = {"at": 0.0, "directions": [], "skills": [], "companies": []}
_TTL = 300.0


@dataclass
class ToolRequest:
    name: str
    args: dict = field(default_factory=dict)
    # Agent 已经执行过的工具把结果带在这里，避免重复执行
    result: dict | None = field(default=None, compare=False, repr=False)


@dataclass
class Route:
    tools: list[ToolRequest] = field(default_factory=list)
    doc_types: list[int] | None = None
    refusal: str | None = None
    instruction: str = ""
    slots: dict = field(default_factory=dict)
    # job_list：逐条保留城市和薪资；skill_list：列出前几名技能，不要收成第一名
    answer_shape: str = ""


_JOB_LIST_INSTRUCTION = (
    "只用一句话说明条数，不要逐条展开，不要把不同职位概括成同一城市或同一薪资。"
    "城市和薪资必须与各条工具结果一致，禁止编造。"
)


def wants_skill_list(text: str) -> bool:
    """「有哪些 / 排行 / top / 前几」列出前几名；带「增长最快」时仍只给第一名。"""
    if re.search(r"增长最快|增速最快|涨得最快|环比最高", text or ""):
        return False
    return bool(re.search(r"有哪些|排行|排名|\btop\b|top\s*\d+|前几|前\s*\d+|哪些", text or "", re.I))


def _lexicon_get() -> tuple[list[tuple[str, str]], list[str], list[str]]:
    now = time.time()
    with _lock:
        if _lexicon["directions"] and now - _lexicon["at"] < _TTL:
            return _lexicon["directions"], _lexicon["skills"], _lexicon["companies"]
    directions: dict[str, str] = {}
    for alias, canonical in DIRECTION_ALIAS.items():
        directions[alias] = canonical
        directions[canonical] = canonical
    skills: set[str] = set()
    companies: set[str] = set()
    try:
        conn = connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT tech_direction FROM job_position
                    WHERE deleted = 0 AND tech_direction IS NOT NULL AND tech_direction <> ''
                    """
                )
                for row in cur.fetchall():
                    name = str(row["tech_direction"]).strip()
                    if name:
                        directions.setdefault(name, name)
                cur.execute(
                    "SELECT name FROM skill_tag WHERE deleted = 0 AND status = 1 AND CHAR_LENGTH(name) >= 2"
                )
                for row in cur.fetchall():
                    skills.add(str(row["name"]).strip())
                cur.execute(
                    """
                    SELECT company_name, short_name FROM ent_company
                    WHERE deleted = 0 AND audit_status = 1
                    """
                )
                for row in cur.fetchall():
                    for key in ("company_name", "short_name"):
                        name = str(row.get(key) or "").strip()
                        if len(name) >= 3:
                            companies.add(name)
        finally:
            conn.close()
    except Exception:
        pass
    pairs = sorted(directions.items(), key=lambda item: len(item[0]), reverse=True)
    skill_list = sorted(skills, key=len, reverse=True)
    company_list = sorted(companies, key=len, reverse=True)
    with _lock:
        _lexicon["at"] = time.time()
        _lexicon["directions"] = pairs
        _lexicon["skills"] = skill_list
        _lexicon["companies"] = company_list
    return pairs, skill_list, company_list


def _find_city(text: str) -> str:
    for city in sorted(CITY_PROVINCE, key=len, reverse=True):
        if city in text or f"{city}市" in text:
            return city
    return ""


def _find_direction(text: str, pairs: list[tuple[str, str]]) -> str:
    for surface, canonical in pairs:
        if surface and surface in text:
            return canonical
    return ""


def _find_education(text: str) -> int | None:
    for label, value in sorted(EDU_TEXT.items(), key=lambda item: len(item[0]), reverse=True):
        if label in {"不限", "学历不限", "不限学历"}:
            continue
        if label in text and int(value) in (1, 2, 3, 4):
            return int(value)
    return None


def _find_skill(text: str, skills: list[str], direction: str) -> str:
    for name in skills:
        if name and name in text and name != direction:
            return name
    return ""


def _find_job_id(text: str) -> int | None:
    matched = re.search(r"(?:职位|岗位)\s*(?:编号|ID|id)?\s*[:：]?\s*(\d{1,8})", text)
    if not matched:
        matched = re.search(r"(?:job|JOB)\s*[:#]?\s*(\d{1,8})", text)
    if not matched:
        return None
    value = int(matched.group(1))
    return value if value > 0 else None


def _find_salary_min(text: str) -> int | None:
    matched = re.search(r"(\d+(?:\.\d+)?)\s*[kK千]", text)
    if matched:
        return int(float(matched.group(1)) * 1000)
    matched = re.search(r"(?:月薪|薪资|工资)\s*(\d{4,6})", text)
    if matched:
        return int(matched.group(1))
    return None


def _find_years(text: str) -> float | None:
    if "应届" in text:
        return 0.0
    matched = re.search(r"(\d+(?:\.\d+)?)\s*年(?:经验|工作)", text)
    if matched:
        return float(matched.group(1))
    return None


def _title_for_jd(text: str) -> str:
    matched = re.search(
        r"(?:写|生成|起草|润色)(?:一份|一个|一则|了|出)?\s*(.+?)(?:的)?(?:JD|jd|职位描述|岗位描述|招聘启事)",
        text,
        re.I,
    )
    if not matched:
        return ""
    title = matched.group(1).strip()
    title = re.sub(r"^(?:一份|一个|一则)", "", title).strip(" 的")
    return title[:40]


def _cross_role_refusal(question: str, role: str) -> str | None:
    if role != "company" and re.search(r"筛选.{0,20}候选人|候选人.{0,8}筛选|筛一下|简历筛选", question):
        return "筛选候选人仅企业招聘助手可用，且只能查看本公司职位下的投递。"
    if role != "company" and re.search(r"(写|生成|起草|润色).{0,40}(JD|jd|职位描述|岗位描述)", question):
        return "生成或润色职位描述仅企业招聘助手可用。"
    if role != "admin" and re.search(r"需求增长最快|推荐评估|NDCG|平台概况|全平台", question, re.I):
        return "全平台统计仅管理员数据助手可以查询。学生可以指定城市和方向做薪资预测。"
    if role != "admin" and re.search(r"平均薪资最高的城市|平台平均薪资|薪资最高的城市", question):
        return "全平台薪资排行仅管理员数据助手可以查询。你可以指定城市和方向，我帮你做薪资预测。"
    if role == "company" and re.search(r"其他公司的职位|别的公司的候选人|学生编号\s*\d+", question):
        return "不能查看其他企业的职位或其他学生的档案。企业只能处理本公司收到的投递。"
    if role != "student" and re.search(r"我的技能还差|我的推荐|适合我的岗位", question):
        return "个人技能差距和个性化推荐仅学生就业助手可用。"
    return None


def _policy_types(question: str) -> list[int]:
    types: list[int] = []
    rules = [
        (r"三方|违约|解约|签约", [6]),
        (r"档案|户口|报到证|落户|派遣", [6]),
        (r"试用期|劳动合同|社保|加班|公积金", [6]),
        (r"政策|补贴|基层|西部计划|三支一扶|特岗|征兵|入伍|学费补偿|创业贷款", [1]),
        (r"简历", [5]),
        (r"面试|群面|STAR|技术面|HR", [3, 5]),
        (r"平台|怎么投|收藏|推荐分|上架", [2]),
        (r"校招|秋招|春招|网申|双选会", [5, 2]),
        (r"招聘须知|职位描述怎么写|发布职位", [4]),
    ]
    for pattern, values in rules:
        if re.search(pattern, question, re.I):
            for value in values:
                if value not in types:
                    types.append(value)
    return types



_COMPANY_ALIASES = [
    ("字节跳动", ["字节跳动", "字节", "Bytedance", "ByteDance"]),
    ("腾讯", ["腾讯", "Tencent"]),
    ("阿里巴巴", ["阿里巴巴", "阿里", "Alibaba"]),
    ("蚂蚁集团", ["蚂蚁集团", "蚂蚁", "Ant"]),
    ("美团", ["美团", "Meituan"]),
    ("小红书", ["小红书", "红书"]),
    ("京东", ["京东", "JD"]),
    ("快手", ["快手", "Kuaishou"]),
    ("百度", ["百度", "Baidu"]),
    ("网易", ["网易", "NetEase"]),
    ("滴滴出行", ["滴滴出行", "滴滴", "DiDi", "Didi"]),
    ("哔哩哔哩", ["哔哩哔哩", "B站", "bilibili", "Bilibili"]),
    ("拼多多", ["拼多多", "PDD"]),
    ("华为", ["华为", "Huawei"]),
    ("小米", ["小米", "Xiaomi"]),
    ("OPPO", ["OPPO", "oppo"]),
    ("vivo", ["vivo", "VIVO"]),
    ("米哈游", ["米哈游", "miHoYo"]),
    ("携程", ["携程", "Ctrip"]),
    ("蔚来", ["蔚来", "NIO"]),
    ("懂车帝", ["懂车帝"]),
    ("理想汽车", ["理想汽车"]),
    ("小鹏汽车", ["小鹏汽车"]),
]


def _find_company(text: str, companies: list[str] | None = None) -> str:
    """从问题中识别校招企业名，返回用于职位检索的关键词。"""
    if not text:
        return ""
    candidates: list[tuple[int, str]] = []
    lowered = text.lower()
    for canonical, aliases in _COMPANY_ALIASES:
        for alias in aliases:
            if not alias:
                continue
            if alias.lower() in lowered:
                candidates.append((len(alias), canonical))
    for name in companies or []:
        if name and name in text:
            candidates.append((len(name), name))
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][1]


def route(question: str, role: str) -> Route:
    """根据角色和问题选择工具与知识库过滤类型。"""
    text = (question or "").strip()
    refusal = _cross_role_refusal(text, role)
    if refusal:
        return Route(refusal=refusal, doc_types=[])
    pairs, skills, companies = _lexicon_get()
    slots = {
        "city": _find_city(text),
        "direction": _find_direction(text, pairs),
        "education": _find_education(text),
        "experience_years": _find_years(text),
        "salary_min": _find_salary_min(text),
        "job_id": _find_job_id(text),
        "keyword": _find_skill(text, skills, ""),
        "title": _title_for_jd(text),
    }
    # 公司名优先作为关键词（支持真实校招企业与外部扩充库企业）
    company_kw = _find_company(text, companies)
    if company_kw:
        slots["keyword"] = company_kw
    if slots["keyword"] and slots["keyword"] == slots["direction"]:
        slots["keyword"] = ""
    result = Route(slots=slots)

    if role == "student":
        return _route_student(text, slots, result)
    if role == "company":
        return _route_company(text, slots, result)
    if role == "admin":
        return _route_admin(text, slots, result)
    result.refusal = "无法识别的角色。"
    result.doc_types = []
    return result


def is_salary_question(text: str, slots: dict | None = None) -> bool:
    """薪资预测或询问某城市/方向能拿多少。"""
    slots = slots or {}
    if re.search(r"薪资预测|能拿多少|工资多少|月薪多少|薪资大概|预测薪资|薪酬多少|能有多少(工资|月薪|薪资)", text or ""):
        return True
    return bool(
        re.search(r"薪资|工资|月薪|薪酬", text or "")
        and (slots.get("city") or slots.get("direction") or slots.get("keyword"))
    )


def _search_jobs_args(slots: dict) -> dict:
    return {
        "keyword": slots.get("keyword"),
        "city": slots.get("city"),
        "direction": slots.get("direction"),
        "education": slots.get("education"),
        "salary_min": slots.get("salary_min"),
        "limit": 5,
    }


def _route_student(text: str, slots: dict, result: Route) -> Route:
    if re.search(r"技能还差|还差什么|技能差距|匹配度|能不能投|差哪些技能|技能差距", text):
        args = {}
        if slots["job_id"]:
            args["job_id"] = slots["job_id"]
        elif slots["keyword"] or slots["direction"]:
            args["keyword"] = slots["keyword"] or slots["direction"]
        result.tools.append(ToolRequest("analyze_resume_gap", args))
        result.doc_types = [5]
        result.instruction = "根据工具给出的匹配技能、缺失技能和匹配比例说明，不要编造简历中没有的技能。"
        return result
    salary = is_salary_question(text, slots)
    wants_jobs = bool(re.search(r"找|搜|有哪些|在招|招聘|推荐几个|看几个|岗位|职位", text)) and not re.search(
        r"三方|违约|档案|户口|试用期|劳动合同|政策补贴", text
    )
    if salary:
        result.tools.append(
            ToolRequest(
                "predict_salary",
                {
                    "city": slots["city"],
                    "direction": slots["direction"],
                    "education": slots["education"],
                    "experience_years": slots["experience_years"],
                },
            )
        )
        result.tools.append(ToolRequest("search_jobs", _search_jobs_args(slots)))
        result.doc_types = [7]
        result.instruction = (
            "先引用工具中的预测月薪和区间，并说明这是估计不是 offer；"
            "再引用在招职位的薪资范围（资料或工具结果），注明是否为估算、来源是企业发布还是外部同步，"
            "不要编造数字，也不要把不同职位概括成同一薪资。"
        )
        return result
    if wants_jobs and re.search(r"找|搜|有哪些|在招|招聘|推荐几个|看几个|岗位|职位", text):
        if re.search(r"我的推荐|适合我|给我推荐", text) and not slots["city"] and not slots["keyword"]:
            result.tools.append(ToolRequest("get_my_recommendations", {"limit": 5}))
            result.doc_types = []
            result.answer_shape = "job_list"
            result.instruction = _JOB_LIST_INSTRUCTION
            return result
        result.tools.append(ToolRequest("search_jobs", _search_jobs_args(slots)))
        result.doc_types = [7]
        result.answer_shape = "job_list"
        result.instruction = _JOB_LIST_INSTRUCTION
        return result
    if re.search(r"我的推荐|适合我的|给我推荐", text):
        result.tools.append(ToolRequest("get_my_recommendations", {"limit": 5}))
        result.doc_types = []
        result.answer_shape = "job_list"
        result.instruction = _JOB_LIST_INSTRUCTION
        return result
    types = _policy_types(text)
    result.doc_types = types or [1, 2, 3, 4, 5, 6]
    result.instruction = "优先依据资料回答；资料不足时说明知识库没有相关信息。"
    return result


# 企业侧可检索的知识库类型：4 企业招聘须知、6 手续 FAQ（劳动合同、三方等用工规则）。
# 1 就业政策、2 平台使用指南（学生视角）、3 面经、5 求职指导都是面向学生的资料，企业兜底不再混入。
COMPANY_DOC_TYPES = (4, 6)

_COMPANY_STATS = re.compile(
    r"(投递|简历|应聘|申请|候选人|招聘).{0,8}(概况|统计|情况|汇总|数量|总数|多少|几份|几个|趋势|进展|分布|数据|漏斗)"
    r"|(收到|新增|来了).{0,8}(多少|几份|几个).{0,4}(简历|投递|申请)?"
    r"|招聘(看板|概况|进度|数据)|待(初筛|处理)的?(简历|投递)|投递漏斗|转化率|录用率",
)


def is_company_stats_question(text: str) -> bool:
    return bool(_COMPANY_STATS.search(text or ""))


def _stats_window(text: str) -> int:
    if re.search(r"今天|今日", text):
        return 1
    if re.search(r"本月|这个月|近一个月|最近一个月|30\s*天|三十天", text):
        return 30
    matched = re.search(r"(?:近|最近|过去)\s*(\d{1,2})\s*天", text)
    if matched:
        return max(1, min(int(matched.group(1)), 90))
    return 7


# 用工合规：即使问句里出现「候选人」，也不应当成筛选候选人。
_COMPLIANCE = re.compile(
    r"合不合规|是否合规|合不合法|违不违法|是否违法|算不算歧视|有没有歧视|歧不歧视|"
    r"只限男|只限女|仅限男|仅限女|只要男|只要女|不要女生|不要男生|"
    r"性别限制|性别要求|婚育限制|收培训费|入职收费|必须购买|收取押金|培训费"
)
_SCREEN = re.compile(
    r"筛选|简历筛选|筛一下|"
    r"(查看|看看|列出|有哪些|帮我看).{0,12}(候选人|投递的人|投递者)|"
    r"(候选人|投递的人).{0,10}(名单|列表|匹配|排序|情况|简历)"
)


def is_compliance_question(text: str) -> bool:
    return bool(_COMPLIANCE.search(text or ""))


def is_screen_question(text: str) -> bool:
    if is_compliance_question(text):
        return False
    return bool(_SCREEN.search(text or ""))


def _route_company(text: str, slots: dict, result: Route) -> Route:
    if is_company_stats_question(text) and not re.search(r"筛选|筛一下|润色|改写|(写|生成|起草).{0,20}(JD|jd|描述)", text):
        result.tools.append(ToolRequest("application_stats", {"days": _stats_window(text)}))
        result.doc_types = []
        result.instruction = (
            "你在为企业 HR 汇报本公司投递数据。只使用工具结果中的数字，按新增投递、状态分布、"
            "投递最多的职位、待办提醒四部分简要说明，并给出一条筛选或优化职位的建议。"
            "不要提及学校就业指导中心或学生求职建议。"
        )
        return result
    if is_compliance_question(text):
        types = [value for value in _policy_types(text) if value in COMPANY_DOC_TYPES]
        result.doc_types = types or list(COMPANY_DOC_TYPES)
        result.instruction = (
            "你在为企业 HR 回答用工合规问题。依据企业招聘须知和劳动用工资料说明，"
            "不要编造审核结论或法条编号；涉及性别限制、入职收费等情形应明确指出不得作为招聘条件。"
            "不要去筛选本公司候选人，不要给出面向学生的求职建议。"
        )
        return result
    if is_screen_question(text):
        args = {}
        if slots["job_id"]:
            args["job_id"] = slots["job_id"]
        result.tools.append(ToolRequest("screen_applicants", args))
        result.doc_types = []
        result.instruction = "按工具给出的匹配比例排序说明候选人，不要评价工具中没有的人。"
        return result
    if re.search(r"润色|改写|优化", text) and re.search(r"描述|JD|jd|职责", text):
        result.tools.append(ToolRequest("polish_job_description", {"text": text[:1200]}))
        result.doc_types = [4]
        result.instruction = "在保留原意的前提下润色成职责、要求、加分项和福利四段，不要新增具体薪资数字。"
        return result
    if re.search(r"写|生成|起草", text) and re.search(r"JD|jd|职位描述|岗位描述|招聘启事", text):
        result.tools.append(
            ToolRequest(
                "generate_job_description",
                {
                    "title": slots["title"] or slots["direction"] or "软件开发工程师",
                    "direction": slots["direction"],
                    "city": slots["city"],
                    "skills": slots["keyword"],
                    "highlights": "",
                },
            )
        )
        result.doc_types = [4]
        result.instruction = "请按四个小标题输出：职位描述、任职要求、加分项、福利。技能只用要点里列出的名称，不要编造年限、学历门槛和具体月薪。福利注明以劳动合同为准。"
        return result
    if re.search(r"我发布的职位|我的职位|在招职位|职位列表", text):
        result.tools.append(ToolRequest("list_my_jobs", {"limit": 8}))
        result.doc_types = []
        result.instruction = "只列出工具返回的本企业职位。"
        return result
    types = [value for value in _policy_types(text) if value in COMPANY_DOC_TYPES]
    result.doc_types = types or list(COMPANY_DOC_TYPES)
    result.instruction = (
        "你在为企业 HR 回答。从企业招聘管理和劳动用工合规角度回答，依据资料，不要编造审核结论；"
        "不要给出面向学生的求职建议，不要建议咨询学校就业指导中心。"
        "涉及本公司投递数据时，提示可以问「本周投递概况」或到「招聘看板」「候选人管理」查看。"
    )
    return result


def _route_admin(text: str, slots: dict, result: Route) -> Route:
    if re.search(r"推荐评估|推荐算法|评估指标|NDCG|Precision|Recall|准确率|召回率", text, re.I):
        result.tools.append(ToolRequest("recommend_eval", {}))
        result.doc_types = []
        result.instruction = "只转述评估表中的指标，不要改写数值。"
        return result
    if re.search(r"需求增长|技术趋势|热门技术|热门技能|什么技术|什么技能|技能热度|技术热度|热门技|最火的技|技能需求|技术需求|增长最快的技|技[术能]增长最快|哪个技[术能]|哪种技[术能]|增速最快的技", text):
        list_style = wants_skill_list(text)
        # 排行问题不要用问句里偶然命中的技能名把结果滤成一条
        result.tools.append(
            ToolRequest("tech_trend", {"skill": "" if list_style else slots["keyword"], "top_n": 5})
        )
        result.doc_types = []
        if list_style:
            result.answer_shape = "skill_list"
            result.instruction = "按工具结果逐条列出技能名称、需求量和环比，不要只写增长最快的一项，不要改数字。"
        else:
            result.instruction = "只采用工具结果第一行结论里的技术名称和环比，不要改成列表中的其他技术。"
        return result
    if _is_city_question(text):
        result.tools.append(ToolRequest("city_distribution", {"top_n": 8}))
        result.doc_types = []
        result.instruction = "只根据工具结论说明岗位最多的城市和各城市职位数，不要改成省份，不要编造没有出现的城市。"
        return result
    if re.search(r"地区分布|省份|热力图|哪个省|哪些省|各省|(岗位|职位)最多", text):
        result.tools.append(ToolRequest("region_distribution", {"top_n": 8}))
        result.doc_types = []
        result.instruction = "按工具中的省份职位数说明地区分布，不要改成城市口径。"
        return result
    if re.search(r"平台概况|有多少|多少用户|多少职位|概览|总体情况", text):
        result.tools.append(ToolRequest("platform_overview", {}))
        result.doc_types = []
        result.instruction = "用简短条目报告人数和职位数。"
        return result
    if re.search(r"薪资|工资|月薪|薪酬", text):
        result.tools.append(
            ToolRequest("salary_stats", {"city": slots["city"], "direction": slots["direction"]})
        )
        result.doc_types = []
        result.instruction = "按平均月薪从高到低说明，并带上样本量。不要推算工具里没有的城市。"
        return result
    result.tools.append(ToolRequest("platform_overview", {}))
    result.doc_types = [1, 2, 3, 4, 5, 6]
    result.instruction = "结合平台概况中的数字和资料回答。没有直接依据时说明知识库没有相关内容，不要编造统计数字。"
    return result


def _is_city_question(text: str) -> bool:
    """城市岗位数量问题走 city_distribution。薪资问题留给后面的薪资统计。"""
    if re.search(r"薪资|工资|月薪|薪酬", text):
        return False
    return bool(
        re.search(
            r"城市分布|各城市|哪些城市|哪个城市|"
            r"城市.{0,12}(岗位|职位).{0,8}(最多|数量|分布|排行)|"
            r"(岗位|职位).{0,10}最多.{0,6}城市",
            text,
        )
    )


def allowed_tool_names(role: str) -> set[str]:
    if role == "student":
        return {"search_jobs", "get_my_recommendations", "predict_salary", "analyze_resume_gap"}
    if role == "company":
        return {
            "generate_job_description",
            "polish_job_description",
            "screen_applicants",
            "list_my_jobs",
            "application_stats",
        }
    if role == "admin":
        return {
            "salary_stats",
            "tech_trend",
            "region_distribution",
            "city_distribution",
            "recommend_eval",
            "platform_overview",
        }
    return set()
