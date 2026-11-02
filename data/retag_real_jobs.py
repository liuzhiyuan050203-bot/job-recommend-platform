"""重新给真实校招职位打技能标签（修正早期导入留下的错误默认标签）。

背景：data/import_real_jobs.py 早期版本把识别不出方向的职位都归到「后端开发」，并补上
Java / Spring Boot / MySQL 作为默认技能；后来方向识别改成运营、销售、设计等岗位归到
「产品经理 / UI设计」，但已入库职位的标签没有重算。结果是 300 多个「游戏体验设计」「渠道运营」
「大客户销售」职位挂着 Java / Spring Boot / MySQL，推荐理由据此写出「与你的 Java/MySQL 技能
匹配」，内容匹配分也被抬高（UX 审计 P1-1）。

处理范围：real_* 企业名下、现有标签里没有一个属于职位自身方向的职位。
新标签：
1. 只看职位名称（真实数据的任职要求字段只有来源信息），按 import_real_jobs.SKILL_KEYWORDS 加上
   产品 / 设计类关键词匹配；英文关键词要求前后不是字母，避免「TS」命中「posts」之类。
2. 研发方向职位，或名称里出现产品经理、产品策划、设计、交互、体验等字样的职位，用方向词表补足到 2 个。
3. 运营、销售、人力等岗位如果名称里没有任何技能词，就不挂技能标签，不再编造。

用法：
  .venv/bin/python data/retag_real_jobs.py            # 预览前 20 条和统计，不写库
  .venv/bin/python data/retag_real_jobs.py --apply    # 写库
执行前先备份（mysqldump）。重复执行是幂等的：修正后的职位已有本方向标签或已无错误标签。
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pymysql

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_real_jobs import SKILL_KEYWORDS, db_config  # noqa: E402

EXTRA_KEYWORDS: list[tuple[str, list[str]]] = [
    ("原型设计", ["原型"]),
    ("需求分析", ["需求分析", "需求调研"]),
    ("Axure", ["Axure"]),
    ("交互设计", ["交互"]),
    ("Figma", ["Figma"]),
    ("Sketch", ["Sketch"]),
    ("C语言", ["C语言"]),
    ("STM32", ["STM32", "单片机"]),
    ("RTOS", ["RTOS"]),
]
# 名称里有这些字样才用方向词表补默认标签（非研发方向）
DEFAULT_CUES = {
    "产品经理": re.compile(r"产品经理|产品策划|产品设计|产品助理|游戏策划"),
    "UI设计": re.compile(r"设计|交互|体验|UI|UX|视觉|美术", re.I),
}
NON_RD = set(DEFAULT_CUES)
# 方向默认标签的优先顺序（其余方向按标签编号）
DEFAULT_ORDER = {"产品经理": ["需求分析", "原型设计", "Axure"], "UI设计": ["交互设计", "Figma", "Sketch"]}


def keyword_pattern(kw: str) -> re.Pattern:
    word = kw.strip()
    if re.fullmatch(r"[A-Za-z0-9.+#/ ]+", word):
        return re.compile(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", re.I)
    return re.compile(re.escape(word), re.I)


KEYWORDS = [(name, [keyword_pattern(k) for k in kws if k.strip()]) for name, kws in SKILL_KEYWORDS + EXTRA_KEYWORDS]


def new_tags(title: str, direction: str, tag_by_name: dict[str, int], tags_by_dir: dict[str, list[int]]) -> list[int]:
    found: list[int] = []
    for name, patterns in KEYWORDS:
        tid = tag_by_name.get(name)
        if tid and any(p.search(title) for p in patterns):
            found.append(tid)
    found = list(dict.fromkeys(found))[:4]
    pool = [tag_by_name[n] for n in DEFAULT_ORDER.get(direction, []) if n in tag_by_name] or tags_by_dir.get(direction, [])
    need_default = direction not in NON_RD or bool(DEFAULT_CUES[direction].search(title))
    if need_default and len(found) < 2:
        for tid in pool:
            if len(found) >= 2:
                break
            if tid not in found:
                found.append(tid)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    conn = pymysql.connect(**db_config())
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, direction FROM skill_tag WHERE deleted=0 ORDER BY id")
            tag_by_name, tags_by_dir, tag_name, tag_dir = {}, {}, {}, {}
            for tid, name, direction in cur.fetchall():
                tag_by_name[name] = tid
                tag_name[tid] = name
                tag_dir[tid] = direction
                tags_by_dir.setdefault(direction, []).append(tid)
            cur.execute(
                """
                SELECT p.id, p.title, p.tech_direction
                FROM job_position p
                JOIN ent_company c ON c.id = p.company_id
                JOIN sys_user u ON u.id = c.user_id
                WHERE p.deleted = 0 AND u.username LIKE 'real\\_%%'
                  AND NOT EXISTS (
                    SELECT 1 FROM job_position_tag pt JOIN skill_tag t ON t.id = pt.tag_id
                    WHERE pt.position_id = p.id AND pt.deleted = 0 AND t.direction = p.tech_direction)
                ORDER BY p.id
                """
            )
            jobs = cur.fetchall()
            cur.execute("SELECT position_id, tag_id FROM job_position_tag WHERE deleted=0")
            current: dict[int, set[int]] = {}
            for pid, tid in cur.fetchall():
                current.setdefault(pid, set()).add(tid)
            removed = added = untagged = 0
            now = datetime.now().replace(microsecond=0)
            for index, (pid, title, direction) in enumerate(jobs):
                old = current.get(pid, set())
                new = new_tags(title or "", direction or "", tag_by_name, tags_by_dir)
                drop = sorted(old - set(new))
                add = [t for t in new if t not in old]
                removed += len(drop)
                added += len(add)
                untagged += 0 if new else 1
                if index < 20:
                    print(f"{pid} [{direction}] {title}: {[tag_name[t] for t in sorted(old)]} -> {[tag_name[t] for t in new]}")
                if not args.apply:
                    continue
                if drop:
                    cur.execute(
                        f"DELETE FROM job_position_tag WHERE position_id=%s AND tag_id IN ({','.join(['%s'] * len(drop))})",
                        [pid, *drop],
                    )
                for tid in add:
                    cur.execute(
                        """INSERT INTO job_position_tag (position_id, tag_id, create_time, update_time, deleted)
                           VALUES (%s,%s,%s,%s,0) ON DUPLICATE KEY UPDATE deleted=0, update_time=VALUES(update_time)""",
                        (pid, tid, now, now),
                    )
            print(f"jobs={len(jobs)} removed_links={removed} added_links={added} now_untagged={untagged} apply={args.apply}")
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
