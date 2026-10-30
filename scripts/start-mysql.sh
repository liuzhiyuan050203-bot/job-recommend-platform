#!/usr/bin/env bash
# Start MariaDB (MySQL-compatible) without systemd, if not already running.
set -e
if sudo mariadb-admin ping --silent 2>/dev/null; then
  echo "MariaDB already running."; exit 0
fi
sudo mkdir -p /run/mysqld && sudo chown mysql:mysql /run/mysqld
sudo service mariadb start || (sudo -u mysql nohup mysqld_safe >/dev/null 2>&1 &)
for i in $(seq 1 30); do
  sudo mariadb-admin ping --silent 2>/dev/null && { echo "MariaDB started."; exit 0; }
  sleep 1
done
echo "MariaDB failed to start; check /var/log/mysql or journal output." >&2; exit 1
