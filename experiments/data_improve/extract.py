#!/usr/bin/env python3
"""(a) 职位文本 → 结构化 JSON：hard_skills / min_education / experience / category。

两种后端，结果都按「后端+模型+提示版本+文本」做 sha1 键缓存到 cache/extract_<backend>.jsonl，重跑零成本：
  rule ：技能词典 + 正则（默认；无大模型时的兜底，确定性）
  llm  ：任意 OpenAI 兼容接口（本机 Ollama qwen2.5:3b 即 http://127.0.0.1:11434/v1）
         环境变量 EXTRACT_LLM_BASE_URL / EXTRACT_LLM_MODEL / EXTRACT_LLM_API_KEY，未设置时沿用 LLM_BASE_URL / LLM_MODEL / LLM_API_KEY
LLM 输出的技能统一过一遍同一技能词典做别名归一，类别限定在平台 12 个方向内，非法 JSON 记为失败并回退规则结果。

  .venv/bin/python experiments/data_improve/extract.py --backend rule
  .venv/bin/python experiments/data_improve/extract.py --backend llm --limit 200     # 抽样 / 对比规则一致率
注意：两份公开数据集（BOSS/51job）与自爬校招职位都没有完整 JD 正文，输入文本是「职位名 + 技能标签 + 福利」。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
CACHE.mkdir(exist_ok=True)
PROMPT_VERSION = "v1"
CATEGORIES = ["后端开发", "前端开发", "移动开发", "测试开发", "数据开发", "算法工程", "人工智能", "运维开发",
              "云原生开发", "嵌入式开发", "产品经理", "UI设计", "其他"]
EDU_NAMES = {0: "不限", 1: "大专", 2: "本科", 3: "硕士", 4: "博士"}

# 规范名 → 别名正则（不区分大小写）
SKILLS = {
    "Java": r"\bjava\b(?!\s*script)", "Python": r"python", "Go": r"\bgo\b|golang", "C++": r"c\+\+|cpp",
    "C": r"(?<![a-z+#])c(?![a-z+#])|c语言", "C#": r"c#|\.net", "PHP": r"\bphp\b", "JavaScript": r"javascript|\bjs\b",
    "TypeScript": r"typescript|\bts\b", "Vue": r"vue", "React": r"react", "Angular": r"angular", "HTML/CSS": r"html|css",
    "Node.js": r"node", "小程序": r"小程序|uniapp|uni-app", "Android": r"android|安卓", "iOS": r"\bios\b|swift|objective",
    "Flutter": r"flutter", "Spring": r"spring(?!\s*boot|\s*cloud)", "SpringBoot": r"spring\s*boot|springboot",
    "SpringCloud": r"spring\s*cloud|springcloud|微服务", "MyBatis": r"mybatis", "Dubbo": r"dubbo",
    "MySQL": r"mysql", "Oracle": r"oracle", "PostgreSQL": r"postgre", "SQL": r"\bsql\b", "Redis": r"redis",
    "MongoDB": r"mongo", "Elasticsearch": r"elastic|\bes\b", "Kafka": r"kafka", "RabbitMQ": r"rabbit|\bmq\b|rocketmq",
    "Hadoop": r"hadoop|hdfs|hive", "Spark": r"spark", "Flink": r"flink", "数据仓库": r"数仓|数据仓库|etl",
    "Linux": r"linux|shell", "Docker": r"docker", "Kubernetes": r"k8s|kubernetes", "DevOps": r"devops|jenkins|ci/cd",
    "云平台": r"aws|阿里云|腾讯云|云计算|openstack", "Nginx": r"nginx", "Netty": r"netty", "高并发": r"高并发|分布式",
    "JVM": r"jvm|多线程|并发编程", "设计模式": r"设计模式", "算法": r"算法|数据结构", "机器学习": r"机器学习|sklearn|xgboost",
    "深度学习": r"深度学习|pytorch|tensorflow|神经网络", "NLP": r"nlp|自然语言", "CV": r"\bcv\b|计算机视觉|图像|opencv",
    "大模型": r"大模型|llm|gpt|aigc|rag", "自动化测试": r"自动化测试|selenium|appium|pytest|unittest|robot",
    "性能测试": r"性能测试|jmeter|loadrunner|压力测试", "接口测试": r"接口测试|postman", "功能测试": r"功能测试|黑盒|手工测试",
    "白盒测试": r"白盒|单元测试", "测试开发": r"测试开发", "嵌入式": r"嵌入式|单片机|stm32|arm|rtos|驱动",
    "FPGA": r"fpga|verilog", "网络": r"tcp|网络协议|路由|交换机", "安全": r"安全|渗透", "Git": r"\bgit\b",
    "Unity": r"unity|unreal|游戏引擎", "UI设计": r"ui设计|figma|sketch|photoshop|\bps\b", "产品设计": r"axure|需求分析|产品设计|原型",
}
_SKILL_RE = {k: re.compile(v, re.I) for k, v in SKILLS.items()}
DIRECTION_RULES = None


def normalize_skills(items) -> list[str]:
    out = []
    for raw in items:
        text = str(raw)
        hit = [k for k, r in _SKILL_RE.items() if r.search(text)]
        out.extend(hit)
    return sorted(set(out))


def rule_extract(row: dict) -> dict:
    global DIRECTION_RULES
    if DIRECTION_RULES is None:
        sys.path.insert(0, str(HERE.parent / "salary"))
        from prepare_real_salary import direction_of  # 与数据清洗同一套方向规则
        DIRECTION_RULES = direction_of
    text = f"{row['title']} {row['skills']}"
    return {"hard_skills": normalize_skills([text]),
            "min_education": EDU_NAMES.get(int(row.get("education", 2)), "本科"),
            "experience": f"{row.get('exp_years', 0)}年", "category": DIRECTION_RULES(text)}


PROMPT = """你是招聘数据结构化助手。只根据下面的职位信息，输出一个 JSON 对象，不要任何解释：
{{"hard_skills": [硬技能名称列表，最多10个，如 Java、MySQL、Vue、Selenium],
 "min_education": "不限|大专|本科|硕士|博士",
 "experience": "如 应届 / 1-3年 / 3-5年 / 不限",
 "category": "{cats}" 中的一个}}
职位名：{title}
技能标签：{skills}
福利：{welfare}
学历要求：{edu}；经验：{exp}"""


class LLM:
    def __init__(self):
        from openai import OpenAI
        base = os.getenv("EXTRACT_LLM_BASE_URL") or os.getenv("LLM_BASE_URL") or "http://127.0.0.1:11434/v1"
        self.model = os.getenv("EXTRACT_LLM_MODEL") or os.getenv("LLM_MODEL") or "qwen2.5:3b"
        key = os.getenv("EXTRACT_LLM_API_KEY") or os.getenv("LLM_API_KEY") or "ollama"
        self.client = OpenAI(base_url=base, api_key=key, timeout=float(os.getenv("EXTRACT_LLM_TIMEOUT", "120")))

    def __call__(self, row: dict) -> dict:
        msg = PROMPT.format(cats="|".join(CATEGORIES), title=row["title"], skills=row["skills"] or "无",
                            welfare=row.get("welfare") or "无", edu=EDU_NAMES.get(int(row.get("education", 2)), "本科"),
                            exp=f"{row.get('exp_years', 0)}年")
        resp = self.client.chat.completions.create(
            model=self.model, temperature=0, max_tokens=200, messages=[{"role": "user", "content": msg}],
            response_format={"type": "json_object"})
        text = resp.choices[0].message.content or ""
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0) if m else text)
        cat = str(data.get("category", "其他")).strip()
        return {"hard_skills": normalize_skills(data.get("hard_skills") or []),
                "raw_skills": [str(s) for s in (data.get("hard_skills") or [])][:10],
                "min_education": str(data.get("min_education", "")), "experience": str(data.get("experience", "")),
                "category": cat if cat in CATEGORIES else "其他"}


def key_of(backend: str, model: str, row: dict) -> str:
    text = f"{backend}|{model}|{PROMPT_VERSION}|{row['title']}|{row['skills']}|{row.get('welfare', '')}|" \
           f"{row.get('education', '')}|{row.get('exp_years', '')}"
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def load_cache(backend: str) -> dict:
    path = CACHE / f"extract_{backend}.jsonl"
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                out[rec["key"]] = rec
    return out


def extract_frame(df: pd.DataFrame, backend: str = "rule", limit: int | None = None, verbose: bool = False) -> dict:
    """返回 {row_id: 结构化结果}；llm 后端未命中缓存且调用失败时回退规则（记 fallback=true）。"""
    model = "rules-v1"
    llm = None
    if backend == "llm":
        llm = LLM()
        model = llm.model
    cache = load_cache(backend) if backend == "llm" else {}
    path = CACHE / f"extract_{backend}.jsonl"
    out, new, t0, fails = {}, 0, time.time(), 0
    rows = df.to_dict("records")
    if limit:
        rows = rows[:limit]
    with open(path, "a", encoding="utf-8") if backend == "llm" else open(os.devnull, "w") as fh:
        for i, row in enumerate(rows):
            if backend == "rule":
                out[row["row_id"]] = rule_extract(row)
                continue
            k = key_of(backend, model, row)
            if k in cache:
                out[row["row_id"]] = cache[k]["result"]
                continue
            try:
                res = llm(row)
                ok = True
            except Exception as exc:  # 非法 JSON / 超时
                res, ok = {**rule_extract(row), "fallback": True, "error": type(exc).__name__}, False
                fails += 1
            out[row["row_id"]] = res
            cache[k] = {"key": k, "model": model, "ok": ok, "result": res}
            fh.write(json.dumps(cache[k], ensure_ascii=False) + "\n")
            fh.flush()
            new += 1
            if verbose and new % 20 == 0:
                print(f"  llm {new} 条新调用，{(time.time() - t0) / new:.1f}s/条，失败 {fails}", flush=True)
    if backend == "llm":
        print(f"llm 抽取：命中缓存 {len(out) - new}，新调用 {new}，失败回退 {fails}")
    return out


def main() -> int:
    from di_common import load_real
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["rule", "llm"], default="rule")
    ap.add_argument("--dataset", default="boss_2023")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sample-seed", type=int, default=None, help="先按种子打乱再取 --limit 条")
    args = ap.parse_args()
    df = load_real(args.dataset)
    if args.sample_seed is not None:
        df = df.sample(frac=1.0, random_state=args.sample_seed)
    res = extract_frame(df, args.backend, args.limit, verbose=True)
    if args.backend == "llm":  # 与规则结果对比一致率
        rule = {r: rule_extract(row) for r, row in zip(df["row_id"], df.to_dict("records")) if r in res}
        cat_agree = sum(res[r]["category"] == rule[r]["category"] for r in res) / max(1, len(res))
        jac = [len(set(res[r]["hard_skills"]) & set(rule[r]["hard_skills"])) /
               max(1, len(set(res[r]["hard_skills"]) | set(rule[r]["hard_skills"]))) for r in res]
        summary = {"n": len(res), "category_agree": round(cat_agree, 3),
                   "skill_jaccard_mean": round(sum(jac) / max(1, len(jac)), 3),
                   "fallback": sum(1 for r in res.values() if r.get("fallback"))}
        print(json.dumps(summary, ensure_ascii=False))
        (HERE / "results" / f"llm_vs_rule_{args.dataset}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"规则抽取 {len(res)} 条；示例：", json.dumps(next(iter(res.values())), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
