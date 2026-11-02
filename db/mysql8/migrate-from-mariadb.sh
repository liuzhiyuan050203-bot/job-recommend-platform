#!/usr/bin/env bash
# 把 MariaDB 导出的 job_platform 全量 SQL 导入 MySQL 8.4，并把 MariaDB 的 JSON 别名列改回 MySQL 原生 JSON。
# 用法：bash db/mysql8/migrate-from-mariadb.sh /path/to/backup_mariadb_job_platform.sql
# 导出（在 MariaDB 仍运行时执行）：
#   mariadb-dump -h127.0.0.1 -ujob -pjob123 --single-transaction --routines --triggers \
#     --default-character-set=utf8mb4 --databases job_platform > backup_mariadb_job_platform.sql
set -euo pipefail
SRC=${1:?需要 MariaDB 导出文件}
source "$(cd "$(dirname "$0")/../../scripts" && pwd)/db-env.sh"
TMP=$(mktemp --suffix=.sql)
trap 'rm -f "$TMP"' EXIT
# MariaDB 11 的导出以 /*M!999999\- enable the sandbox mode */ 开头，MySQL 客户端不认识，去掉所有 /*M! 行
grep -v '^/\*M!' "$SRC" > "$TMP"
"$MYSQL_BIN" --no-defaults --protocol=tcp -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASS" \
  --default-character-set=utf8mb4 < "$TMP" 2> >(grep -v 'Using a password' >&2)
# MariaDB 把 JSON 存成 LONGTEXT + CHECK(json_valid(...))，在 MySQL 中改回 JSON，与 db/schema.sql 一致
for spec in "spark_task_log params_json 任务参数" "spark_salary_predict feature_json 回归特征向量"; do
  set -- $spec
  chk=$(db_sql "SELECT cc.CONSTRAINT_NAME FROM information_schema.CHECK_CONSTRAINTS cc JOIN information_schema.TABLE_CONSTRAINTS tc USING (CONSTRAINT_SCHEMA, CONSTRAINT_NAME) WHERE tc.TABLE_SCHEMA='$DB_NAME' AND tc.TABLE_NAME='$1' AND cc.CHECK_CLAUSE LIKE '%json_valid%'")
  [ -n "$chk" ] && db_sql "ALTER TABLE $1 DROP CHECK $chk"
  db_sql "ALTER TABLE $1 MODIFY COLUMN $2 JSON NULL COMMENT '$3'"
done
echo "导入完成，各表行数："
for t in $(db_sql "SHOW TABLES"); do echo "$t $(db_sql "SELECT COUNT(*) FROM \`$t\`")"; done
