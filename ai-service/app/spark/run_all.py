"""命令行入口: python -m app.spark.run_all [--tasks clean,aggregate,salary_regression]

混合推荐单独执行: python -m app.spark.run_all --tasks recommend
"""

from __future__ import annotations

import argparse
import sys

from app.spark.db import connect
from app.spark.runner import SparkBusyError, run_blocking


def _print_samples() -> None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            print("薪资统计样例:")
            cur.execute(
                """
                SELECT province, city, tech_direction, job_count, avg_salary, median_salary
                FROM spark_salary_stat
                WHERE is_latest=1 AND deleted=0
                ORDER BY avg_salary DESC
                LIMIT 5
                """
            )
            for row in cur.fetchall():
                print(
                    f"  {row['province']}/{row['city']} {row['tech_direction']} "
                    f"n={row['job_count']} avg={row['avg_salary']} median={row['median_salary']}"
                )
            print("地区分布样例:")
            cur.execute(
                """
                SELECT province_name, adcode, job_count, company_count, avg_salary, apply_count
                FROM spark_region_dist
                WHERE is_latest=1 AND deleted=0
                ORDER BY job_count DESC
                LIMIT 5
                """
            )
            for row in cur.fetchall():
                print(
                    f"  {row['province_name']} {row['adcode']} jobs={row['job_count']} "
                    f"companies={row['company_count']} avg={row['avg_salary']} apply={row['apply_count']}"
                )
            print("技术趋势样例（最近月需求最高）:")
            cur.execute(
                """
                SELECT stat_month, tag_name, demand_count, avg_salary, mom_rate
                FROM spark_tech_trend
                WHERE is_latest=1 AND deleted=0
                ORDER BY stat_month DESC, demand_count DESC
                LIMIT 5
                """
            )
            for row in cur.fetchall():
                print(
                    f"  {row['stat_month']} {row['tag_name']} demand={row['demand_count']} "
                    f"avg={row['avg_salary']} mom={row['mom_rate']}"
                )
            print("各表最新批次行数:")
            for table in ("spark_salary_stat", "spark_tech_trend", "spark_region_dist", "spark_salary_predict"):
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM {table} WHERE is_latest=1 AND deleted=0"
                )
                print(f"  {table} {cur.fetchone()['cnt']}")
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行 Spark 清洗、聚合、薪资回归或混合推荐")
    parser.add_argument(
        "--tasks",
        default="clean,aggregate,salary_regression",
        help="逗号分隔：clean,aggregate,salary_regression,recommend。默认不含 recommend",
    )
    args = parser.parse_args(argv)
    tasks = [item.strip() for item in args.tasks.split(",") if item.strip()]
    try:
        result = run_blocking(tasks)
    except SparkBusyError as exc:
        print(exc)
        return 1
    except ValueError as exc:
        print(exc)
        return 1
    print(f"batch_no={result['batchNo']} 总耗时 {result['elapsedSeconds']}s")
    failed = False
    for task in result["tasks"]:
        if task["status"] == 1:
            print(
                f"  [{task['taskCode']}] {task['elapsedSeconds']}s "
                f"in={task.get('inputCount')} out={task.get('outputCount')} {task.get('resultMsg')}"
            )
        else:
            failed = True
            print(f"  [{task['taskCode']}] 失败 {task['elapsedSeconds']}s {task.get('errorMsg')}")
        _print_recommend_metrics(task)
    if not failed and any(item["taskCode"] != "recommend" for item in result["tasks"]):
        _print_samples()
    return 1 if failed else 0


def _print_recommend_metrics(task: dict) -> None:
    params = task.get("params") or {}
    metrics = params.get("metrics") or []
    if not metrics:
        return
    print(
        f"  协同过滤={params.get('cfMethod')} alpha={params.get('alpha')} "
        f"fusion={params.get('fusion')} adaptive={params.get('adaptiveAlpha')}"
    )
    print(f"  {params.get('cfChoiceReason')}")
    print(f"  {'算法':<10}{'K':>4}{'P@K':>10}{'R@K':>10}{'NDCG':>10}{'覆盖率':>10}")
    for row in metrics:
        print(
            f"  {row['algo']:<10}{row['k']:>4}{row['precision']:>10.4f}"
            f"{row['recall']:>10.4f}{row['ndcg']:>10.4f}{row['coverage']:>10.4f}"
        )


if __name__ == "__main__":
    sys.exit(main())
