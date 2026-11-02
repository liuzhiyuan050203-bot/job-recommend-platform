#!/usr/bin/env bash
# 启动 MySQL 8.4（服务 mysql8，无 systemd 时走 /etc/init.d 脚本），已在运行则直接返回。
set -e
source "$(cd "$(dirname "$0")" && pwd)/db-env.sh"
if db_ping; then
  echo "MySQL $(db_version) 已在运行。"; exit 0
fi
if [ ! -x "/etc/init.d/$DB_SERVICE" ]; then
  echo "未找到 /etc/init.d/$DB_SERVICE，请先按 db/README.md 安装 MySQL 8.4。" >&2; exit 1
fi
sudo service "$DB_SERVICE" start
for i in $(seq 1 30); do
  db_ping && { echo "MySQL $(db_version) 已启动。"; exit 0; }
  sleep 1
done
echo "MySQL 启动失败，查看 /var/log/mysql8/error.log。" >&2; exit 1
