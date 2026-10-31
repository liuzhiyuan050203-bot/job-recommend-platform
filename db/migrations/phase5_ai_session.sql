-- 阶段五 AI 会话：ai_message 增加 extra，保存助手消息的来源、工具和耗时。
-- 可重复执行。不删除已有消息。
-- 用法：mariadb -h127.0.0.1 -ujob -pjob123 job_platform < db/migrations/phase5_ai_session.sql

SET NAMES utf8mb4;

SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_message' AND COLUMN_NAME = 'extra'
);
SET @sql := IF(
  @exists = 0,
  'ALTER TABLE ai_message ADD COLUMN extra TEXT NULL COMMENT ''助手附带信息，JSON 文本，含 sources、tools、latency_ms、first_token_ms'' AFTER content',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
