"""特征工程（第 2 步）：职级/岗位类型规则、公司档位、福利标记、结构化技能、bge 文本向量 PCA。

所有「需要拟合」的东西（类别取值、技能词表、PCA）只在训练集上 fit，黄金集只 transform。
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent

# ---------- (c) 标题 → 职级 / 岗位类型 ----------
SENIORITY_RULES = [  # 先匹配高等级
    (6, r"总监|首席|CTO|VP|副总"),
    (5, r"专家|架构师|架构|技术经理|项目经理|负责人|主管|leader|Leader|组长|TL\b|经理"),
    (4, r"高级|资深|Senior|senior|Sr\.?|SR|高工|骨干|主程"),
    (2, r"初级|助理|Junior|junior|助教"),
    (1, r"校招|应届|毕业生|培训生|管培|储备|校园"),
    (0, r"实习|Intern|intern"),
]
TYPE_FLAGS = {
    "is_outsource": r"外包|驻场|外派|派遣|人力|驻点",
    "is_intern": r"实习|Intern|intern",
    "is_campus": r"校招|应届|毕业生|培训生|管培|储备",
    "is_manager": r"经理|主管|总监|负责人|组长|leader|Leader",
    "is_parttime": r"兼职|远程|临时",
}


def seniority_of(title: str) -> int:
    for level, pat in SENIORITY_RULES:
        if re.search(pat, title or ""):
            return level
    return 3  # 中级 / 未注明


def title_features(df: pd.DataFrame) -> pd.DataFrame:
    t = df["title"].fillna("")
    out = pd.DataFrame(index=df.index)
    out["seniority"] = t.map(seniority_of).astype(float)
    for name, pat in TYPE_FLAGS.items():
        out[name] = t.str.contains(pat, regex=True).astype(float)
    return out


# ---------- (b) 公司档位 ----------
TIERS = ["头部大厂", "外企", "国企/央企/金融科技子公司", "上市/大型民企", "中型企业", "小型/创业", "外包/人力服务"]


def _tier_table() -> list[tuple[re.Pattern, str]]:
    tab = pd.read_csv(HERE / "company_tier.csv")
    return [(re.compile(p, re.I), t) for p, t in zip(tab["pattern"], tab["tier"])]


_TABLE = None


def tier_of(name: str, size: float, ctype: str = "") -> str:
    global _TABLE
    if _TABLE is None:
        _TABLE = _tier_table()
    text = f"{name or ''} {ctype or ''}"
    # 外包优先：华为驻场、阿里外包等按外包计
    for pat, tier in _TABLE:
        if tier == "外包/人力服务" and pat.search(text):
            return tier
    for pat, tier in _TABLE:
        if pat.search(text):
            return tier
    if ctype in ("国企", "事业单位"):
        return "国企/央企/金融科技子公司"
    if ctype.startswith("外资") or ctype in ("合资", "外企代表处"):
        return "外企"
    if ctype == "上市公司" or size >= 6:
        return "上市/大型民企"
    if ctype == "创业公司" or 0 < size <= 2:
        return "小型/创业"
    if size >= 4:
        return "中型企业"
    return "小型/创业" if size > 0 else "中型企业"


def company_tier(df: pd.DataFrame) -> pd.Series:
    return pd.Series([tier_of(n, s, c) for n, s, c in zip(df["company_name"], df["company_size"], df["company_type"])],
                     index=df.index)


# ---------- 福利标记 ----------
WELFARE_FLAGS = {
    "wf_stock": r"股票|期权",
    "wf_bonus": r"年终奖",
    "wf_13pay": r"十三薪|13薪|十四薪|14薪|十五薪",
    "wf_board": r"包吃|包住|住宿|宿舍",
    "wf_shuttle": r"班车",
    "wf_flex": r"弹性",
    "wf_med": r"补充医疗|商业保险|体检",
    "wf_overtime": r"加班补助|加班费",
}


def welfare_features(df: pd.DataFrame) -> pd.DataFrame:
    w = df["welfare"].fillna("")
    out = pd.DataFrame(index=df.index)
    for name, pat in WELFARE_FLAGS.items():
        out[name] = w.str.contains(pat, regex=True).astype(float)
    out["wf_count"] = w.map(lambda s: len([x for x in re.split(r"[,，、;；\s]+", s) if x])).astype(float)
    return out


# ---------- (a) 结构化技能：来自抽取器缓存（LLM 或规则），见 extract.py ----------
def skill_lists(df: pd.DataFrame, extracted: dict) -> list[list[str]]:
    return [extracted.get(rid, {}).get("hard_skills", []) for rid in df["row_id"]]


class Featurizer:
    """在训练集上 fit，产出稠密数值矩阵（供 Spark VectorAssembler 与 LightGBM 共用）。"""

    def __init__(self, groups: list[str], skill_vocab: int = 150, skill_min_df: int = 5, pca_dim: int = 16):
        self.groups, self.skill_vocab, self.skill_min_df, self.pca_dim = groups, skill_vocab, skill_min_df, pca_dim

    def fit(self, df: pd.DataFrame, extracted: dict | None = None, emb: np.ndarray | None = None):
        self.cities = sorted(df["city"].unique())
        self.dirs = sorted(df["tech_direction"].unique())
        self.industries = df["industry"].replace("", "未知").value_counts().head(30).index.tolist()
        if "skills" in self.groups:
            from collections import Counter
            c = Counter(s for lst in skill_lists(df, extracted) for s in set(lst))
            self.vocab = [s for s, n in c.most_common(self.skill_vocab) if n >= self.skill_min_df]
        if "llmcat" in self.groups:
            self.cats = sorted({extracted.get(r, {}).get("category", "其他") for r in df["row_id"]})
        if "emb" in self.groups:
            from sklearn.decomposition import PCA
            self.pca = PCA(n_components=self.pca_dim, random_state=42).fit(emb)
        return self

    @staticmethod
    def _onehot(values: pd.Series, levels: list[str], prefix: str) -> pd.DataFrame:
        return pd.DataFrame({f"{prefix}={lv}": (values == lv).astype(float) for lv in levels}, index=values.index)

    def transform(self, df: pd.DataFrame, extracted: dict | None = None, emb: np.ndarray | None = None) -> pd.DataFrame:
        parts = [self._onehot(df["city"], self.cities, "city"), self._onehot(df["tech_direction"], self.dirs, "dir"),
                 df[["city_tier", "edu_years", "exp_years"]].astype(float)]
        g = self.groups
        if "company" in g:
            parts += [df[["company_size"]].astype(float),
                      self._onehot(df["industry"].replace("", "未知"), self.industries, "ind")]
        if "title" in g:
            parts.append(title_features(df))
        if "tier" in g:
            parts.append(self._onehot(company_tier(df), TIERS, "tier"))
        if "welfare" in g:
            parts.append(welfare_features(df))
        if "skills" in g:
            lists = skill_lists(df, extracted)
            m = pd.DataFrame({f"sk={s}": [float(s in set(lst)) for lst in lists] for s in self.vocab}, index=df.index)
            m["n_hard_skills"] = [float(len(lst)) for lst in lists]
            parts.append(m)
        if "llmcat" in g:
            cats = pd.Series([extracted.get(r, {}).get("category", "其他") for r in df["row_id"]], index=df.index)
            parts.append(self._onehot(cats, self.cats, "cat"))
        if "emb" in g:
            z = self.pca.transform(emb)
            parts.append(pd.DataFrame(z, index=df.index, columns=[f"pca{i}" for i in range(z.shape[1])]))
        if "year" in g:
            parts.append(df[["data_year"]].astype(float))
        X = pd.concat(parts, axis=1)
        X.columns = [re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff=+#.]", "_", c) for c in X.columns]
        return X
