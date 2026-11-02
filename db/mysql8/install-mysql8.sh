#!/usr/bin/env bash
# 在 Debian 13 上安装 MySQL 8.4.13 LTS（官方 Linux Generic 二进制包，minimal 版已含 mysql / mysqldump / mysqladmin）。
# Debian 13 官方源没有 mysql-server，且 apt 安装会与 MariaDB 包冲突，所以用二进制包装到 /opt，与 MariaDB 并存。
# 与本机实际执行的步骤一致；需要 sudo。用法：bash db/mysql8/install-mysql8.sh
set -euo pipefail
VER=${MYSQL_VERSION:-8.4.13}
PKG=mysql-${VER}-linux-glibc2.28-x86_64-minimal
HERE=$(cd "$(dirname "$0")" && pwd)
DL=${DL_DIR:-/tmp}

if [ ! -x "/opt/mysql-${VER}/bin/mysqld" ]; then
  [ -f "$DL/$PKG.tar.xz" ] || curl -fSL -o "$DL/$PKG.tar.xz" "https://cdn.mysql.com/Downloads/MySQL-8.4/$PKG.tar.xz"
  tar -xJf "$DL/$PKG.tar.xz" -C "$DL"
  sudo mv "$DL/$PKG" "/opt/mysql-${VER}"
fi
sudo ln -sfn "/opt/mysql-${VER}" /opt/mysql

# Debian 13 只有 libaio.so.1t64，mysqld 需要 libaio.so.1：在 MySQL 私有库目录里建软链，不动系统库
sudo apt-get install -y -q libaio1t64 >/dev/null
[ -e /opt/mysql/lib/private/libaio.so.1 ] || sudo ln -s /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /opt/mysql/lib/private/libaio.so.1

id mysql >/dev/null 2>&1 || sudo useradd -r -s /bin/false mysql
sudo mkdir -p /etc/mysql8 /var/lib/mysql8 /var/log/mysql8
sudo cp "$HERE/my.cnf" /etc/mysql8/my.cnf
sudo cp "$HERE/mysql8.init" /etc/init.d/mysql8 && sudo chmod +x /etc/init.d/mysql8
sudo chown mysql:mysql /var/lib/mysql8 /var/log/mysql8 && sudo chmod 750 /var/lib/mysql8
if [ ! -d /var/lib/mysql8/mysql ]; then
  sudo /opt/mysql/bin/mysqld --defaults-file=/etc/mysql8/my.cnf --initialize-insecure --user=mysql
fi
sudo service mysql8 start
# root 只允许本机 root 用户经 socket 登录（auth_socket），应用使用 job 账号
sudo /opt/mysql/bin/mysql --defaults-file=/etc/mysql8/my.cnf -uroot <<'SQL'
INSTALL PLUGIN auth_socket SONAME 'auth_socket.so';
ALTER USER 'root'@'localhost' IDENTIFIED WITH auth_socket;
CREATE DATABASE IF NOT EXISTS job_platform DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'job'@'127.0.0.1' IDENTIFIED BY 'job123';
CREATE USER IF NOT EXISTS 'job'@'localhost' IDENTIFIED BY 'job123';
GRANT ALL PRIVILEGES ON job_platform.* TO 'job'@'127.0.0.1';
GRANT ALL PRIVILEGES ON job_platform.* TO 'job'@'localhost';
FLUSH PRIVILEGES;
SQL
sudo update-rc.d mysql8 defaults >/dev/null 2>&1 || true
echo "MySQL $(/opt/mysql/bin/mysqld --version | awk '{print $3}') 已安装并启动。"
