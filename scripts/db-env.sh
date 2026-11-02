#!/usr/bin/env bash
# 数据库公共变量与函数（被 start-all / stop-all / start-mysql / tests 引用）。
# 数据库：MySQL 8.4 LTS（8.4.13，官方 Linux Generic 二进制包，安装在 /opt/mysql），
# 服务名 mysql8（/etc/init.d/mysql8），配置 /etc/mysql8/my.cnf（仓库副本 db/mysql8/my.cnf）。
# 客户端优先用 $MYSQL_HOME/bin 下的 MySQL 自带程序；不存在时退回 PATH 里的 mysql / mysqladmin。
# 全部走 TCP 127.0.0.1:3306，并用 --no-defaults 避免读到其他发行版留下的 /etc/mysql/my.cnf。
MYSQL_HOME=${MYSQL_HOME:-/opt/mysql}
DB_HOST=${DB_HOST:-127.0.0.1}
DB_PORT=${DB_PORT:-3306}
DB_USER=${DB_USER:-job}
DB_PASS=${DB_PASS:-job123}
DB_NAME=${DB_NAME:-job_platform}
DB_SERVICE=${DB_SERVICE:-mysql8}
if [ -x "$MYSQL_HOME/bin/mysql" ]; then
  MYSQL_BIN="$MYSQL_HOME/bin/mysql"
  MYSQLADMIN_BIN="$MYSQL_HOME/bin/mysqladmin"
else
  MYSQL_BIN=$(command -v mysql || echo mysql)
  MYSQLADMIN_BIN=$(command -v mysqladmin || echo mysqladmin)
fi

# db_ping：数据库可用返回 0
db_ping() {
  "$MYSQLADMIN_BIN" --no-defaults --protocol=tcp -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASS" ping --silent >/dev/null 2>&1
}

# db_sql "SQL"：在业务库执行，-N 不输出列名；stderr（含密码提示）丢弃
db_sql() {
  "$MYSQL_BIN" --no-defaults --protocol=tcp -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASS" \
    --default-character-set=utf8mb4 -N "$DB_NAME" -e "$1" 2>/dev/null
}

# db_version：输出服务端版本，如 8.4.13
db_version() { db_sql "SELECT VERSION()"; }
