"""spark_* 表的读写。新批次与旧批次切换放在同一个事务里。"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import settings

ALLOWED_TABLES = {
    "spark_salary_stat",
    "spark_tech_trend",
    "spark_region_dist",
    "spark_salary_predict",
    "spark_recommend",
    "spark_recommend_eval",
    "spark_user_neighbor",
}
KEEP_BATCHES = 5


def connect():
    return pymysql.connect(
        host=settings.MYSQL_HOST,
        port=int(settings.MYSQL_PORT),
        user=settings.MYSQL_USER,
        password=settings.MYSQL_PASSWORD,
        database=settings.MYSQL_DB,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=DictCursor,
    )


def _dumps(payload: Any) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False, default=str)


def clip(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    value = str(text)
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def start_task(batch_no: str, task_code: str, task_name: str, params: dict | None = None) -> int:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO spark_task_log
                    (batch_no, task_code, task_name, status, start_time, params_json, deleted)
                VALUES (%s, %s, %s, 0, %s, %s, 0)
                """,
                (batch_no, task_code, task_name, datetime.now(), _dumps(params or {})),
            )
            return int(cur.lastrowid)
    finally:
        conn.close()


def finish_task(
    task_id: int,
    status: int,
    input_count: int | None = None,
    output_count: int | None = None,
    result_msg: str | None = None,
    error_msg: str | None = None,
    params: dict | None = None,
) -> None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE spark_task_log
                SET status=%s, end_time=%s, input_count=%s, output_count=%s,
                    result_msg=%s, error_msg=%s, params_json=%s
                WHERE id=%s
                """,
                (
                    status,
                    datetime.now(),
                    input_count,
                    output_count,
                    clip(result_msg, 500),
                    clip(error_msg, 4000),
                    _dumps(params),
                    task_id,
                ),
            )
    finally:
        conn.close()


def fail_unfinished(batch_no: str, task_names: dict[str, str], tasks: list[str], error_msg: str) -> int:
    """批次子进程异常退出时收尾：仍为运行中（0）的任务改为失败；一个任务都没写入的批次补写失败记录。

    返回被改写或补写的行数，任务日志表因此不会留下永远“运行中”的记录。
    """
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE spark_task_log SET status=2, end_time=%s, error_msg=%s WHERE batch_no=%s AND status=0",
                (datetime.now(), clip(error_msg, 4000), batch_no),
            )
            changed = int(cur.rowcount or 0)
            cur.execute("SELECT task_code FROM spark_task_log WHERE batch_no=%s", (batch_no,))
            seen = {row["task_code"] for row in cur.fetchall()}
            now = datetime.now()
            for code in tasks:
                if code in seen:
                    continue
                cur.execute(
                    """
                    INSERT INTO spark_task_log
                        (batch_no, task_code, task_name, status, start_time, end_time, error_msg, params_json, deleted)
                    VALUES (%s, %s, %s, 2, %s, %s, %s, %s, 0)
                    """,
                    (batch_no, code, task_names.get(code, code), now, now, clip(error_msg, 4000),
                     _dumps({"batchNo": batch_no, "taskCode": code})),
                )
                changed += 1
            return changed
    finally:
        conn.close()


def _insert(cur, table: str, columns: list[str], rows: list[tuple]) -> None:
    if table not in ALLOWED_TABLES:
        raise RuntimeError(f"不允许写入表 {table}")
    if not rows:
        raise RuntimeError(f"{table} 没有可写入的数据")
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    for offset in range(0, len(rows), 400):
        cur.executemany(sql, rows[offset : offset + 400])


def _prune(cur, table: str, keep: int = KEEP_BATCHES) -> int:
    cur.execute(f"SELECT batch_no, MAX(id) AS mid FROM {table} GROUP BY batch_no ORDER BY mid DESC")
    batches = [row["batch_no"] for row in cur.fetchall()]
    stale = batches[keep:]
    if not stale:
        return 0
    marks = ", ".join(["%s"] * len(stale))
    cur.execute(f"DELETE FROM {table} WHERE batch_no IN ({marks})", stale)
    return int(cur.rowcount)


def publish(
    batch_no: str,
    payloads: list[tuple[str, list[str], list[tuple]]],
    activate_tables: list[str] | None = None,
) -> dict[str, int]:
    """插入 is_latest=1 的新批次，成功后把同表旧批次置 0，并只保留最近 5 批。

    activate_tables 中的表已由 Spark JDBC 以 is_latest=0 追加好本批次数据，这里在同一事务里
    把本批次切为 1、其余批次切为 0 并清理。插入、切换和清理在一个事务内提交。
    失败则回滚，已生效的 latest 数据不变。
    """
    if not payloads and not activate_tables:
        return {}
    conn = connect()
    counts: dict[str, int] = {}
    try:
        conn.autocommit(False)
        with conn.cursor() as cur:
            for table, columns, rows in payloads:
                _insert(cur, table, columns, rows)
                counts[table] = len(rows)
            for table, _columns, _rows in payloads:
                cur.execute(
                    f"UPDATE {table} SET is_latest=0 WHERE batch_no<>%s AND is_latest=1 AND deleted=0",
                    (batch_no,),
                )
                _prune(cur, table)
            for table in activate_tables or []:
                if table not in ALLOWED_TABLES:
                    raise RuntimeError(f"不允许写入表 {table}")
                cur.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE batch_no=%s", (batch_no,))
                counts[table] = int(cur.fetchone()["n"])
                cur.execute(f"UPDATE {table} SET is_latest=1 WHERE batch_no=%s AND deleted=0", (batch_no,))
                cur.execute(
                    f"UPDATE {table} SET is_latest=0 WHERE batch_no<>%s AND is_latest=1 AND deleted=0",
                    (batch_no,),
                )
                _prune(cur, table)
        conn.commit()
        return counts
    except Exception:
        conn.rollback()
        _discard(batch_no, activate_tables or [])
        raise
    finally:
        conn.close()


def _discard(batch_no: str, tables: list[str]) -> None:
    """发布失败时删掉已由 Spark 追加但未生效的本批次行。"""
    if not tables:
        return
    try:
        conn = connect()
        try:
            with conn.cursor() as cur:
                for table in tables:
                    if table in ALLOWED_TABLES:
                        cur.execute(f"DELETE FROM {table} WHERE batch_no=%s AND is_latest=0", (batch_no,))
        finally:
            conn.close()
    except Exception:
        pass


def write_dataframe(frame, table: str) -> None:
    """用 Spark JDBC 把 DataFrame 追加到 spark_* 表（各分区并行写，Driver 不收集数据）。"""
    if table not in ALLOWED_TABLES:
        raise RuntimeError(f"不允许写入表 {table}")
    from app.spark.session import jdbc_url

    (
        frame.write.format("jdbc")
        .option("url", jdbc_url() + "&rewriteBatchedStatements=true")
        .option("driver", "com.mysql.cj.jdbc.Driver")
        .option("user", settings.MYSQL_USER)
        .option("password", settings.MYSQL_PASSWORD)
        .option("dbtable", table)
        .option("batchsize", "2000")
        .mode("append")
        .save()
    )


def _parse_json(value):
    if value is None or isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _plain(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


def task_view(row: dict) -> dict:
    return {
        "id": row["id"],
        "batchNo": row["batch_no"],
        "taskCode": row["task_code"],
        "taskName": row["task_name"],
        "status": row["status"],
        "startTime": _plain(row["start_time"]),
        "endTime": _plain(row["end_time"]),
        "inputCount": row["input_count"],
        "outputCount": row["output_count"],
        "resultMsg": row["result_msg"],
        "errorMsg": row["error_msg"],
        "paramsJson": _parse_json(row["params_json"]),
    }


def list_tasks(current: int = 1, size: int = 10, batch_no: str | None = None) -> dict:
    current = 1 if current < 1 else current
    size = 10 if size < 1 else min(size, 100)
    where = "WHERE deleted=0"
    args: list[Any] = []
    if batch_no:
        where += " AND batch_no=%s"
        args.append(batch_no)
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM spark_task_log {where}", args)
            total = int(cur.fetchone()["total"])
            cur.execute(
                f"""
                SELECT id, batch_no, task_code, task_name, status, start_time, end_time,
                       input_count, output_count, result_msg, error_msg, params_json
                FROM spark_task_log {where}
                ORDER BY id DESC
                LIMIT %s OFFSET %s
                """,
                [*args, size, (current - 1) * size],
            )
            records = [task_view(row) for row in cur.fetchall()]
        return {"records": records, "total": total, "current": current, "size": size}
    finally:
        conn.close()


def tasks_of_batch(batch_no: str) -> list[dict]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, batch_no, task_code, task_name, status, start_time, end_time,
                       input_count, output_count, result_msg, error_msg, params_json
                FROM spark_task_log
                WHERE deleted=0 AND batch_no=%s
                ORDER BY id
                """,
                (batch_no,),
            )
            return [task_view(row) for row in cur.fetchall()]
    finally:
        conn.close()


def latest_regression_metrics(batch_no: str | None = None) -> dict | None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            if batch_no:
                cur.execute(
                    """
                    SELECT params_json FROM spark_task_log
                    WHERE deleted=0 AND task_code='salary_regression' AND batch_no=%s
                    ORDER BY id DESC LIMIT 1
                    """,
                    (batch_no,),
                )
            else:
                cur.execute(
                    """
                    SELECT params_json FROM spark_task_log
                    WHERE deleted=0 AND task_code='salary_regression' AND status=1
                    ORDER BY id DESC LIMIT 1
                    """
                )
            row = cur.fetchone()
        if not row:
            return None
        payload = _parse_json(row["params_json"])
        return payload if isinstance(payload, dict) else None
    finally:
        conn.close()


def find_salary_predict(city: str, tech_direction: str, education: int, experience_years: float) -> dict | None:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT province, city, tech_direction, education, experience_years,
                       predicted_salary, ci_low, ci_high, model_version, feature_json, batch_no
                FROM spark_salary_predict
                WHERE deleted=0 AND is_latest=1 AND city=%s AND tech_direction=%s
                  AND education=%s AND ABS(experience_years - %s) < 0.05
                ORDER BY id DESC
                LIMIT 1
                """,
                (city, tech_direction, education, experience_years),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {key: _plain(value) for key, value in row.items()}
    finally:
        conn.close()
