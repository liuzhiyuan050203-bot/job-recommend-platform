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


def build_reason(
    skill_names: list[str],
    skill_percent: int,
    direction: str,
    city: str,
    direction_match: bool,
    city_match: bool,
    major: str,
    major_match: bool,
    cf_score: float,
    popular: bool,
) -> str:
    """拼一条不超过 255 字的中文推荐理由。"""
    parts: list[str] = []
    if skill_names and skill_percent > 0:
        shown = "/".join(skill_names[:3])
        parts.append(f"与你的 {shown} 技能匹配度 {int(skill_percent)}%")
    if major_match and major:
        parts.append(f"与你的{major}专业相关")
    if direction_match and direction:
        parts.append(f"符合你期望的{direction}方向")
    if city_match and city:
        parts.append(f"位于你期望的城市{city}")
    if cf_score >= 55:
        parts.append("与你相似的同学也投递了该职位")
    elif popular and cf_score < 25:
        parts.append("热门职位")
    if not parts:
        parts.append("热门职位" if popular else "综合你的技能与求职意向推荐")
    text = "；".join(parts)
    if len(text) > 255:
        return text[:252] + "..."
    return text


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
