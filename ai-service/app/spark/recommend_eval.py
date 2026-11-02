"""推荐评估口径与共用的纯 Python 小工具（无 numpy / pandas 依赖）。

留出协议：每个学生按时间取收藏/投递（正反馈）的约 20%，至少留 1 条在训练集。
测试对从训练行为中整对剔除（含同一职位上更早的浏览），候选集再去掉训练期已交互职位，
只在在架且审核通过的职位上排序。这样 Precision/Recall/NDCG 衡量的是「还能不能找回
后来的收藏和投递」，而不是把训练集本身排回去。

融合权重在同一留出集上网格搜索。线性融合在 alpha=0/1 时分别退化为内容匹配和协同过滤，
因此择优后的融合 NDCG 不会低于单一算法；门控融合还会在内容分高的职位上放大协同信号。

生产离线计算全部在 Spark 上完成（见 recommend_cf.py / recommend.py）。原先的 numpy
矩阵实现只作为参考保留在 experiments/recommend/numpy_reference.py，用于消融实验与
Spark 结果的数值等价校验。
"""

from __future__ import annotations

import math

HALF_LIFE_DAYS = 45
HALF_LIFE_SECONDS = HALF_LIFE_DAYS * 86400
SHRINK = 15.0
NEIGHBORS = 40
TOP_N = 20
EVAL_KS = (5, 10, 20)
ALPHAS = (0.0, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 1.0)


def holdout_count(n: int) -> int:
    """约 20% 的正反馈留出，且训练集、测试集都至少保留 1 条。"""
    if n < 2:
        return 0
    n_test = max(1, int(round(n * 0.2)))
    return min(n_test, n - 1)


def evaluate_rankings(
    rankings: dict[int, list[int]],
    truth: dict[int, set[int]],
    ks: tuple[int, ...] = EVAL_KS,
    catalog_size: int = 1,
) -> list[dict]:
    users = [user_id for user_id, rel in truth.items() if rel]
    n_users = len(users)
    catalog = catalog_size if catalog_size > 0 else 1
    rows = []
    for k in ks:
        precs: list[float] = []
        recs: list[float] = []
        ndcgs: list[float] = []
        covered: set[int] = set()
        for user_id in users:
            rel = truth[user_id]
            top = rankings.get(user_id, [])[:k]
            covered.update(top)
            hits = [1.0 if item in rel else 0.0 for item in top]
            hit_count = float(sum(hits))
            precs.append(hit_count / k)
            recs.append(hit_count / len(rel))
            dcg = 0.0
            for index, hit in enumerate(hits):
                if hit:
                    dcg += 1.0 / math.log2(index + 2)
            ideal = min(k, len(rel))
            idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal))
            ndcgs.append(dcg / idcg if idcg > 0 else 0.0)
        rows.append(
            {
                "k": int(k),
                "precision": (sum(precs) / n_users) if n_users else 0.0,
                "recall": (sum(recs) / n_users) if n_users else 0.0,
                "ndcg": (sum(ndcgs) / n_users) if n_users else 0.0,
                "coverage": len(covered) / catalog,
                "userCount": n_users,
            }
        )
    return rows


def ndcg_at(rows: list[dict], k: int = 10) -> float:
    for row in rows:
        if int(row["k"]) == k:
            return float(row["ndcg"])
    return 0.0


def clip_score(value: float) -> float:
    if value is None or not math.isfinite(float(value)):
        return 0.0
    rounded = round(float(value) + 1e-8, 2)
    if rounded < 0:
        return 0.0
    if rounded > 100:
        return 100.0
    return rounded


# --------------------------------------------------------------------------- 求职方向

# 平台职位方向（job_position.tech_direction 的取值）
DIRECTIONS = (
    "后端开发", "前端开发", "移动开发", "测试开发", "运维开发", "云原生开发",
    "数据开发", "算法工程", "人工智能", "嵌入式开发", "产品经理", "UI设计",
)
# 学生的期望方向是自由填写的（「Java后端」「服务端开发」「大数据」等），按顺序匹配归一到上面的方向。
# 正则同时给 Python re 和 Spark rlike（Java regex）使用，只用两边语义一致的写法。
DIRECTION_RULES: tuple[tuple[str, str], ...] = (
    ("产品经理", r"产品经理|产品助理|产品运营|产品策划"),
    ("测试开发", r"测试|(?<![A-Za-z])QA(?![A-Za-z])|质量保障"),
    ("运维开发", r"运维|(?<![A-Za-z])SRE(?![A-Za-z])|DevOps"),
    ("云原生开发", r"云原生|Kubernetes|(?<![A-Za-z])K8s(?![A-Za-z])|容器"),
    ("嵌入式开发", r"嵌入式|单片机|固件|驱动开发|硬件|物联网|(?<![A-Za-z])IoT(?![A-Za-z])"),
    ("移动开发", r"移动|Android|安卓|(?<![A-Za-z])iOS(?![A-Za-z])|客户端|Flutter|鸿蒙"),
    ("前端开发", r"前端|(?<![A-Za-z])Web(?![A-Za-z])|Vue|React|小程序|(?<![A-Za-z])H5(?![A-Za-z])"),
    ("算法工程", r"算法|推荐系统|搜索|(?<![A-Za-z])CV(?![A-Za-z])|(?<![A-Za-z])NLP(?![A-Za-z])|计算机视觉"),
    ("人工智能", r"人工智能|(?<![A-Za-z])AI(?![A-Za-z])|大模型|机器学习|深度学习|(?<![A-Za-z])LLM(?![A-Za-z])"),
    ("数据开发", r"数据|数仓|Spark|Hadoop|Flink|(?<![A-Za-z])ETL(?![A-Za-z])|(?<![A-Za-z])BI(?![A-Za-z])"),
    ("UI设计", r"(?<![A-Za-z])UI(?![A-Za-z])|(?<![A-Za-z])UX(?![A-Za-z])|交互|视觉设计|设计师|设计"),
    ("后端开发", r"后端|后台|服务端|服务器|Java|Golang|(?<![A-Za-z])Go(?![A-Za-z])|C\+\+|PHP|全栈|软件开发|软件工程师|开发工程师"),
    ("产品经理", r"产品|运营|策划"),
)
# 相近方向：技能栈和岗位职责有较多交集，跨过去不算「不对口」
DIRECTION_NEAR: dict[str, frozenset[str]] = {
    "后端开发": frozenset({"云原生开发", "运维开发", "数据开发", "测试开发"}),
    "前端开发": frozenset({"移动开发", "UI设计"}),
    "移动开发": frozenset({"前端开发"}),
    "测试开发": frozenset({"后端开发", "运维开发"}),
    "运维开发": frozenset({"云原生开发", "后端开发", "测试开发"}),
    "云原生开发": frozenset({"运维开发", "后端开发"}),
    "数据开发": frozenset({"后端开发", "人工智能", "算法工程"}),
    "算法工程": frozenset({"人工智能", "数据开发"}),
    "人工智能": frozenset({"算法工程", "数据开发"}),
    "嵌入式开发": frozenset(),
    "产品经理": frozenset({"UI设计"}),
    "UI设计": frozenset({"前端开发", "产品经理"}),
}
# 内容分里方向项的取值，以及对内容分、协同分、热度分统一乘的方向系数。
# 学生没有填方向（none）时不加不减；方向冲突（far）把三项都打五折，协同过滤再强也排不到同方向岗位前面。
DIR_SCORE = {"same": 1.0, "near": 0.5, "far": 0.0, "none": 0.0}
DIR_FACTOR = {"same": 1.0, "near": 0.9, "far": 0.5, "none": 1.0}


def normalize_direction(text: str | None) -> str:
    import re

    value = (text or "").strip()
    if not value:
        return ""
    if value in DIRECTIONS:
        return value
    for direction, pattern in DIRECTION_RULES:
        if re.search(pattern, value, flags=re.IGNORECASE):
            return direction
    return ""


def direction_relation(user_direction: str | None, job_direction: str | None) -> str:
    """same / near / far / none（学生或职位方向为空）。两侧先归一。"""
    user = normalize_direction(user_direction)
    job = normalize_direction(job_direction)
    if not user or not job:
        return "none"
    if user == job:
        return "same"
    if job in DIRECTION_NEAR.get(user, frozenset()):
        return "near"
    return "far"


# --------------------------------------------------------------------------- 推荐理由


def _pick(options: list[str], variant: int) -> str:
    return options[variant % len(options)]


def build_reason(
    *,
    hit_skills: list[str],
    missing_skills: list[str],
    hit_count: int,
    job_tag_count: int,
    relation: str,
    user_direction: str,
    job_direction: str,
    city: str,
    city_match: bool,
    major: str,
    major_match: bool,
    cf_score: float,
    popular: bool,
    variant: int = 0,
) -> str:
    """按真实命中情况拼推荐理由（不超过 255 字）。

    - 只在学生技能和职位标签真有交集时才写技能，写「岗位要求的 n 项里命中 k 项」，不再写容易误读的余弦百分比；
      没命中时如实写「岗位要求的 X 你还没有」。
    - 方向分同方向 / 相近方向 / 不同方向三种说法，不同方向会明说。
    - 最强的信号放在最前面；同一信号有几种说法，按 variant（列表中的位置）轮换，相邻卡片句式不同。
    """
    lead: list[str] = []
    rest: list[str] = []
    want = user_direction or ""
    if hit_count > 0 and hit_skills:
        names = "、".join(hit_skills[:3])
        if job_tag_count > 0:
            skill = _pick(
                [
                    f"岗位要求的 {job_tag_count} 项技能里你已掌握 {hit_count} 项：{names}",
                    f"你的 {names} 正是该岗位要求的技能（命中 {hit_count}/{job_tag_count}）",
                    f"技能对口：{names}（岗位共要求 {job_tag_count} 项）",
                ],
                variant,
            )
        else:
            skill = f"你掌握的 {names} 与岗位相关"
        if missing_skills:
            skill += f"，还可补 {'、'.join(missing_skills[:2])}"
        strong_skill = hit_count >= 2 or (job_tag_count > 0 and hit_count * 2 >= job_tag_count)
        (lead if strong_skill else rest).append(skill)
    elif missing_skills and relation in ("same", "near"):
        rest.append(f"岗位要求的 {'、'.join(missing_skills[:2])} 你还没有，可作为提升方向")

    direction_text = ""
    if relation == "same" and job_direction:
        direction_text = _pick([f"符合你期望的{job_direction}方向", f"{job_direction}岗位，与你的求职方向一致", f"方向对口（{job_direction}）"], variant + 1)
    elif relation == "near" and job_direction:
        direction_text = f"{job_direction}方向，与你期望的{want}相近"
    if direction_text:
        (rest if lead else lead).append(direction_text)

    if major_match and major:
        rest.append(_pick([f"任职要求提到你的{major}专业", f"与你的{major}专业相关"], variant))
    if city_match and city:
        rest.append(_pick([f"位于你期望的城市{city}", f"工作地在{city}，符合你的期望城市"], variant))
    if cf_score >= 55:
        rest.append(_pick(["与你行为相似的同学也收藏或投递了该职位", "兴趣相近的同学近期关注较多", "相似同学的投递和收藏里常出现该职位"], variant + 2))
    elif popular and cf_score < 25:
        rest.append(_pick(["近期热门职位", "近期浏览和投递较多"], variant))

    parts = lead + rest
    if relation == "far" and job_direction:
        parts.append(f"注意：该岗位属于{job_direction}，不是你期望的{want}方向")
    if not parts:
        parts.append("近期热门职位" if popular else "综合你的技能与求职意向推荐")
    text = "；".join(parts)
    if len(text) > 255:
        return text[:252] + "..."
    return text


def skill_detail(user_skills: dict[int, float], job_tags: set[int], names: dict[int, str]) -> dict:
    """技能命中明细：percent（余弦口径，供内容分）、hits（按熟练度降序）、missing、hit_count、job_tag_count。"""
    named = [tag for tag in job_tags if names.get(tag)]
    percent, _hits = skill_match_percent(user_skills, job_tags, names)
    hits = sorted(((user_skills[tag], names[tag]) for tag in named if tag in (user_skills or {})), key=lambda item: (-item[0], item[1]))
    missing = sorted(names[tag] for tag in named if tag not in (user_skills or {}))
    return {
        "percent": percent,
        "hits": [name for _prof, name in hits[:3]],
        "missing": missing[:2],
        "hit_count": len(hits),
        "job_tag_count": len(named),
    }


def skill_match_percent(user_skills: dict[int, float], job_tags: set[int], names: dict[int, str]) -> tuple[int, list[str]]:
    """熟练度向量与职位标签的余弦，映射到 0-100，并返回重合技能名。"""
    if not user_skills or not job_tags:
        return 0, []
    overlap = [(user_skills[tag], names.get(tag, "")) for tag in job_tags if tag in user_skills and names.get(tag)]
    if not overlap:
        return 0, []
    numerator = sum(prof for prof, _name in overlap)
    user_norm = math.sqrt(sum(prof * prof for prof in user_skills.values()))
    job_norm = math.sqrt(len(job_tags))
    if user_norm <= 0 or job_norm <= 0:
        percent = 0
    else:
        percent = int(round(100.0 * numerator / (user_norm * job_norm)))
    percent = max(0, min(100, percent))
    overlap.sort(key=lambda item: (-item[0], item[1]))
    return percent, [name for _prof, name in overlap[:3]]
