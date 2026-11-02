# MySQL 8.4 部署与从 MariaDB 迁移

本项目数据库为 **MySQL 8.4.13 LTS**（MySQL Community Server - GPL，官方 Linux Generic 二进制包 `mysql-8.4.13-linux-glibc2.28-x86_64-minimal.tar.xz`）。早期开发用的是 MariaDB 11.8.6，2026-11-02 迁移到 MySQL 8.4。

| 项 | 值 |
| --- | --- |
| 程序 | `/opt/mysql` → `/opt/mysql-8.4.13`（含 `mysqld`、`mysql`、`mysqladmin`、`mysqldump`） |
| 配置 | `/etc/mysql8/my.cnf`（仓库副本 `db/mysql8/my.cnf`） |
| 数据目录 | `/var/lib/mysql8` |
| 错误日志 | `/var/log/mysql8/error.log` |
| 服务 | `sudo service mysql8 start|stop|restart|status`（`/etc/init.d/mysql8`，仓库副本 `db/mysql8/mysql8.init`） |
| 监听 | `127.0.0.1:3306`，socket `/run/mysqld8/mysqld.sock` |
| 字符集 | `utf8mb4` / `utf8mb4_unicode_ci`，时区 `+08:00`，`sql_mode` 为 MySQL 8.4 默认（含 `ONLY_FULL_GROUP_BY`） |
| 账号 | 应用 `job` / `job123`（`job@127.0.0.1`、`job@localhost`，只有 `job_platform.*` 权限）；`root@localhost` 用 `auth_socket`，只能 `sudo /opt/mysql/bin/mysql --defaults-file=/etc/mysql8/my.cnf -uroot` |

Debian 13 官方源没有 `mysql-server`，apt 装 MySQL 又会和 MariaDB 包冲突，所以用二进制包装在 `/opt`，与 MariaDB 并存。Debian 13 只有 `libaio.so.1t64`，安装脚本在 `/opt/mysql/lib/private/` 里建了 `libaio.so.1` 软链。

## 全新安装

```bash
bash db/mysql8/install-mysql8.sh                 # 下载、初始化、建库建账号、启动
mysql() { /opt/mysql/bin/mysql --no-defaults --protocol=tcp -h127.0.0.1 -ujob -pjob123 "$@"; }
mysql job_platform < db/schema.sql
for f in db/migrations/*.sql; do mysql job_platform < "$f"; done
mysql job_platform < db/seed.sql
```

## 从 MariaDB 迁移（本机实际做法）

1. MariaDB 运行时全量导出：`mariadb-dump ... --databases job_platform > backup_mariadb_job_platform.sql`（本机备份在 `/workspace/bishe-logs/stack/backup_mariadb_job_platform.sql`，53 MB）。
2. `sudo service mariadb stop`（不卸载，数据目录 `/var/lib/mysql` 原样保留）。
3. `bash db/mysql8/install-mysql8.sh`。
4. `bash db/mysql8/migrate-from-mariadb.sh backup_mariadb_job_platform.sql`：去掉 MariaDB 专有的 `/*M!...*/` 行后导入，再把 `spark_task_log.params_json`、`spark_salary_predict.feature_json` 从 MariaDB 的 `LONGTEXT + CHECK(json_valid)` 改回 MySQL 原生 `JSON`。
5. 核对：29 张表行数与 MariaDB 逐表一致（合计 230385 行）；`information_schema.COLUMNS` 的列名、类型、可空、默认值与在 MySQL 上直接执行 `db/schema.sql` 的结果完全一致。

改动的 MariaDB 专有写法：`db/migrations/phase5_rag.sql` 的 `ALTER TABLE ... DROP CONSTRAINT IF EXISTS`（MySQL 不支持）改为先查 `information_schema.TABLE_CONSTRAINTS` 再 `DROP CHECK`，两种数据库都能重复执行。脚本与测试里的 `mariadb` / `mariadb-admin` 命令统一换成 `scripts/db-env.sh` 中的 `db_ping` / `db_sql`（调用 `/opt/mysql/bin` 下的 MySQL 客户端）。后端本来就用 `mysql-connector-j`，ai-service 用 PyMySQL，新增 `cryptography` 依赖以支持 MySQL 8 默认的 `caching_sha2_password` 认证。

## 回退到 MariaDB

MariaDB 11.8.6 已停止并禁用开机启动，未卸载，数据目录 `/var/lib/mysql` 保留的是迁移时刻的数据。回退：

```bash
sudo service mysql8 stop && sudo update-rc.d mysql8 disable
sudo update-rc.d mariadb enable && sudo service mariadb start
export DB_SERVICE=mariadb      # 让 scripts/start-mysql.sh、stop-all.sh --with-mysql 操作 MariaDB
```

`scripts/db-env.sh` 的 `db_ping` / `db_sql` 走 TCP，用 MySQL 客户端连 MariaDB 同样可用。迁移后写进 MySQL 的数据不会自动回到 MariaDB，需要时用 `/opt/mysql/bin/mysqldump` 导出再导入。
