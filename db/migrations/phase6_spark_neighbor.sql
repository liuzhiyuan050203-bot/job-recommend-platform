-- Spark 用户近邻表：离线 Spark 计算用户余弦 Top-40 邻居，实时推荐直接读取。
-- 可重复执行，不影响已有数据。
-- 用法：mysql -h127.0.0.1 -ujob -pjob123 job_platform < db/migrations/phase6_spark_neighbor.sql

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS spark_user_neighbor (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  batch_no      VARCHAR(32)  NOT NULL COMMENT '批次号，逻辑关联 spark_task_log.batch_no',
  user_id       BIGINT       NOT NULL COMMENT '学生，逻辑关联 sys_user.id',
  neighbor_id   BIGINT       NOT NULL COMMENT '相似学生，逻辑关联 sys_user.id',
  similarity    DOUBLE       NOT NULL COMMENT '收缩后相似度：余弦 × co/(co+15)，大于 0',
  cosine        DOUBLE       NOT NULL COMMENT '衰减隐式评分向量的原始余弦',
  co_count      INT          NOT NULL COMMENT '共同交互职位数',
  rank_no       INT          NOT NULL COMMENT '邻居名次，从 1 开始，每个学生最多 40 个',
  is_latest     TINYINT      NOT NULL DEFAULT 0 COMMENT '是否当前生效批次：0否 1是（Spark 先以 0 追加，发布事务内切换）',
  create_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted       TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_spark_user_neighbor (batch_no, user_id, neighbor_id),
  KEY idx_spark_user_neighbor_user (user_id, is_latest, deleted, rank_no),
  CONSTRAINT chk_spark_user_neighbor_rank CHECK (rank_no >= 1),
  CONSTRAINT chk_spark_user_neighbor_latest CHECK (is_latest IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Spark 离线用户近邻（用户余弦 Top-40），供实时推荐复用';
