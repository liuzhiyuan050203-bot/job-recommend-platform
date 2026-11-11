#!/usr/bin/env python3
"""下载并清洗两份公开的、带真实薪资区间的中文招聘数据集（MIT 许可）。

一条命令：  .venv/bin/python experiments/salary/prepare_real_salary.py

数据源（固定 commit，保证可复现）：
  R1 BOSS直聘 2023：github.com/poboll/bosszhipin_spider @3d70ae39（数据文件于 2023-05-08 提交）
  R2 前程无忧 2018：github.com/wangjksjtu/Data-Mining-51Job @31e9a014（数据文件于 2018-06-25 提交）
输出：data/real_salary/boss_2023.csv、data/real_salary/job51_2018.csv 与 manifest.json
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import jieba
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "experiments" / "data" / "raw"
OUT = REPO / "data" / "real_salary"
RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
jieba.setLogLevel(60)

BOSS_SHA = "3d70ae397a61b288c416ec7995d8e6f6216f6d31"
JOB51_SHA = "31e9a014ed6399f0d650fb177ef664a6d03b04fe"
SOURCES = {
    "boss_java": ("poboll/bosszhipin_spider", BOSS_SHA, "merged_java.xlsx"),
    "boss_backend": ("poboll/bosszhipin_spider", BOSS_SHA, "merged_后端开发.xlsx"),
    "boss_test": ("poboll/bosszhipin_spider", BOSS_SHA, "merged_测试工程师.xlsx"),
    "boss_license": ("poboll/bosszhipin_spider", BOSS_SHA, "LICENSE"),
    "job51_middle": ("wangjksjtu/Data-Mining-51Job", JOB51_SHA, "data/middleData.csv"),
    "job51_license": ("wangjksjtu/Data-Mining-51Job", JOB51_SHA, "LICENSE"),
}

CITY_PROVINCE = {
    "北京": "北京", "上海": "上海", "深圳": "广东", "广州": "广东", "杭州": "浙江", "南京": "江苏",
    "苏州": "江苏", "厦门": "福建", "成都": "四川", "武汉": "湖北", "天津": "天津", "西安": "陕西",
    "长沙": "湖南", "合肥": "安徽", "重庆": "重庆", "郑州": "河南", "济南": "山东", "青岛": "山东",
    "大连": "辽宁", "沈阳": "辽宁", "昆明": "云南", "福州": "福建", "宁波": "浙江", "东莞": "广东",
    "佛山": "广东", "珠海": "广东", "惠州": "广东", "无锡": "江苏", "昆山": "江苏", "嘉兴": "浙江",
    "香港": "香港",
}
TIER1 = {"北京", "上海", "深圳", "广州"}
TIER2 = {"杭州", "南京", "苏州", "厦门", "成都", "武汉", "西安", "天津"}

# 标题/职类 → 平台 12 个技术方向（按顺序匹配，先具体后宽泛）。未命中记为“其他”。
DIRECTION_RULES = [
    ("测试开发", r"测试|QA|质量保证"),
    ("算法工程", r"算法"),
    ("人工智能", r"人工智能|机器学习|深度学习|AI|NLP|自然语言|计算机视觉|图像|语音|大模型"),
    ("数据开发", r"大数据|数据开发|数据库|数据仓库|数仓|ETL|数据分析|数据挖掘|BI|Hadoop|Spark"),
    ("前端开发", r"前端|Web前端|H5|HTML|Vue|React|Flash"),
    ("移动开发", r"手机|移动|Android|安卓|iOS|IOS|APP|App|小程序|鸿蒙"),
    ("UI设计", r"UI|UE|UX|交互设计|视觉设计|美工|网页设计|界面设计"),
    ("嵌入式开发", r"嵌入式|单片机|驱动|FPGA|硬件|电子工程|电子技术"),
    ("云原生开发", r"云原生|云计算|云平台|K8s|Kubernetes|容器|DevOps|SRE"),
    ("运维开发", r"运维|网络管理|系统管理员|网络工程师|DBA|技术支持|网络维修|系统工程师|系统集成"),
    ("产品经理", r"产品经理|产品专员|产品总监|产品助理|需求工程师"),
    ("后端开发", r"Java|JAVA|java|后端|后台|PHP|Python|python|Golang|Go|C\+\+|C#|\.NET|\.Net|软件工程师|软件开发|开发工程师|架构|全栈|服务端|程序员|ERP技术开发|研发工程师"),
]


def direction_of(text: str) -> str:
    for name, pattern in DIRECTION_RULES:
        if re.search(pattern, text or ""):
            return name
    return "其他"


def tier_of(city: str) -> int:
    return 1 if city in TIER1 else 2 if city in TIER2 else 3


def fetch(key: str) -> Path:
    repo, sha, rel = SOURCES[key]
    target = RAW / f"{key}{Path(rel).suffix}"
    if not target.exists():
        url = f"https://raw.githubusercontent.com/{repo}/{sha}/{urllib.parse.quote(rel)}"
        print("下载", url)
        with urllib.request.urlopen(url, timeout=120) as resp:
            target.write_bytes(resp.read())
    return target


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tokens_of(*texts: str) -> str:
    words = []
    for text in texts:
        for w in jieba.lcut(str(text or "")):
            w = w.strip().lower()
            if len(w) >= 2 or re.match(r"[a-z]", w):
                if not re.fullmatch(r"[\W_]+", w):
                    words.append(w)
    return " ".join(words)


SIZE_ORD = {"0-20": 1, "少于50人": 1, "20-99": 2, "50-150人": 2, "100-499": 3, "150-500人": 3,
            "500-999": 4, "500-1000人": 4, "1000-9999": 5, "1000-5000人": 5, "5000-10000人": 6,
            "10000以上": 7, "10000人以上": 7}


def prepare_boss(stats: dict) -> pd.DataFrame:
    frames = []
    for key in ("boss_java", "boss_backend", "boss_test"):
        d = pd.read_excel(fetch(key))
        d["keyword_group"] = key.split("_")[1]
        frames.append(d)
    raw = pd.concat(frames, ignore_index=True)
    stats["boss_raw_rows"] = int(len(raw))
    key_cols = ["职位", "薪酬", "地区", "公司名称", "工作经验", "学历要求", "技能要求"]
    raw = raw.drop_duplicates(key_cols).copy()
    stats["boss_after_dedup"] = int(len(raw))

    pat = re.compile(r"^\s*(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)K(?:·(\d+)薪)?\s*$")
    rows, drop = [], {"非月薪(日薪/时薪等)": 0, "实习(天/周或月)": 0, "学历超出平台口径": 0, "城市无省份映射": 0}
    edu_map = {"学历不限": 0, "大专": 1, "本科": 2, "硕士": 3, "博士": 4}
    exp_map = {"在校/应届": 0.0, "应届生": 0.0, "1年以内": 0.5, "1-3年": 2.0, "3-5年": 4.0, "5-10年": 7.5,
               "10年以上": 10.0, "经验不限": 1.0}
    for _, r in raw.iterrows():
        m = pat.match(str(r["薪酬"]))
        if not m:
            drop["非月薪(日薪/时薪等)"] += 1
            continue
        exp = str(r["工作经验"]).strip()
        edu = str(r["学历要求"]).strip()
        if exp not in exp_map:
            drop["实习(天/周或月)"] += 1
            continue
        if edu not in edu_map:
            drop["学历超出平台口径"] += 1
            continue
        city = str(r["地区"]).strip()
        if city not in CITY_PROVINCE:
            drop["城市无省份映射"] += 1
            continue
        low, high = float(m.group(1)) * 1000, float(m.group(2)) * 1000
        title = str(r["职位"]).strip()
        skills = " ".join(str(r["技能要求"]).split()) if pd.notna(r["技能要求"]) else ""
        rows.append({
            "source": "boss_2023", "title": title, "city": city, "province": CITY_PROVINCE[city],
            "city_tier": tier_of(city), "education": edu_map[edu], "exp_years": exp_map[exp],
            "tech_direction": direction_of(title + " " + skills),
            "company_size": SIZE_ORD.get(str(r["公司规模"]).strip(), 0),
            "industry": str(r["公司类型"]).strip() if pd.notna(r["公司类型"]) else "未知",
            "skills": skills, "salary_min": low, "salary_max": high,
            "salary_months": int(m.group(3)) if m.group(3) else 12,
            "avg_salary": (low + high) / 2, "tokens": tokens_of(title, skills),
            "keyword_group": r["keyword_group"],
            # 以下为数据改善实验（experiments/data_improve）追加的列，生产模型按列名读取，不受影响
            "company_name": str(r["公司名称"]).strip() if pd.notna(r["公司名称"]) else "",
            "company_type": "",
            "welfare": str(r["福利"]).strip() if pd.notna(r["福利"]) else "",
            "row_id": "b23_" + hashlib.sha1("|".join(str(r[c]) for c in key_cols).encode("utf-8")).hexdigest()[:12],
        })
    stats["boss_dropped"] = drop
    df = pd.DataFrame(rows)
    stats["boss_clean_rows"] = int(len(df))
    return df


def prepare_job51(stats: dict) -> pd.DataFrame:
    d = pd.read_csv(fetch("job51_middle"), encoding="gbk")
    stats["job51_raw_rows"] = int(len(d))
    edu_map = {"无": 0, "大专": 1, "本科": 2, "硕士": 3, "博士": 4}
    exp_map = {"无工作经验": 0.0, "1年经验": 1.0, "2年经验": 2.0, "3-4年经验": 3.5, "5-7年经验": 6.0,
               "8-9年经验": 8.5, "10年以上经验": 10.0}
    rows, drop = [], {"学历超出平台口径": 0, "城市非具体城市(其他/国外/省名)": 0, "月薪越界(<1000或>100000)": 0, "非IT职类": 0}
    for idx, r in enumerate(d.itertuples(index=False)):
        edu = str(r.education)
        if edu not in edu_map:
            drop["学历超出平台口径"] += 1
            continue
        city = str(r.area)
        if city not in CITY_PROVINCE:
            drop["城市非具体城市(其他/国外/省名)"] += 1
            continue
        low, high = float(r.salary_min) / 12.0, float(r.salary_max) / 12.0
        avg = (low + high) / 2
        if not (1000 <= avg <= 100000):
            drop["月薪越界(<1000或>100000)"] += 1
            continue
        t1 = "" if pd.isna(r.job_work_type_1) else str(r.job_work_type_1)
        t2 = "" if pd.isna(r.job_work_type_2) or str(r.job_work_type_2) == "null" else str(r.job_work_type_2)
        direction = direction_of(t1 + " " + t2)
        if direction == "其他":
            drop["非IT职类"] += 1
            continue
        industry = "未知" if pd.isna(r.company_service_1) else str(r.company_service_1)
        rows.append({
            "source": "job51_2018", "title": (t1 + ("/" + t2 if t2 else "")), "city": city,
            "province": CITY_PROVINCE[city], "city_tier": tier_of(city), "education": edu_map[edu],
            "exp_years": exp_map.get(str(r.work_experience), 1.0), "tech_direction": direction,
            "company_size": SIZE_ORD.get(str(r.company_people), 0), "industry": industry,
            "skills": "", "salary_min": round(low, 2), "salary_max": round(high, 2), "salary_months": 12,
            "avg_salary": round(avg, 2), "tokens": tokens_of(t1, t2), "keyword_group": "it_all",
            "company_name": "",
            "company_type": "" if pd.isna(r.company_type) else str(r.company_type),
            "welfare": "" if pd.isna(r.welfare) else str(r.welfare),
            "row_id": f"j18_{idx:06d}",
        })
    stats["job51_dropped"] = drop
    df = pd.DataFrame(rows)
    stats["job51_clean_rows"] = int(len(df))
    return df


def main() -> int:
    stats: dict = {}
    boss = prepare_boss(stats)
    job51 = prepare_job51(stats)
    boss.to_csv(OUT / "boss_2023.csv", index=False)
    job51.to_csv(OUT / "job51_2018.csv", index=False)
    (OUT / "LICENSE.bosszhipin_spider.txt").write_bytes(fetch("boss_license").read_bytes())
    (OUT / "LICENSE.Data-Mining-51Job.txt").write_bytes(fetch("job51_license").read_bytes())
    manifest = {
        "sources": {k: {"repo": v[0], "commit": v[1], "path": v[2], "sha256": sha256(fetch(k))} for k, v in SOURCES.items()},
        "stats": stats,
        "boss_direction_counts": boss["tech_direction"].value_counts().to_dict(),
        "job51_direction_counts": job51["tech_direction"].value_counts().to_dict(),
        "boss_avg_salary": boss["avg_salary"].describe().round(1).to_dict(),
        "job51_avg_salary": job51["avg_salary"].describe().round(1).to_dict(),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest["stats"], ensure_ascii=False, indent=2))
    print("BOSS 方向:", manifest["boss_direction_counts"])
    print("51job 方向:", manifest["job51_direction_counts"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
