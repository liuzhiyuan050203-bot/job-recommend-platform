-- 职位数据来源字段（数据改善 step2）：区分平台发布 / 自爬核心库 / 外部扩充库。
-- 可重复执行，不删数据。用法：
--   /opt/mysql/bin/mysql --no-defaults -h127.0.0.1 -ujob -pjob123 job_platform < db/migrations/phase7_job_data_source.sql
--   platform   企业在平台上发布（含 seed 与 demo_ 演示企业）
--   self_crawl 自爬核心库：data/import_real_jobs.py 从 16 家大厂校招官网同步（ent_company.credit_code 以 REAL 开头）
--   ext_ats    外部扩充库：data/import_ats_jobs.py 从飞书招聘公开门户同步（credit_code 以 EXTA 开头），前台排在核心库之后

SET NAMES utf8mb4;

SET @has_col := (SELECT COUNT(*) FROM information_schema.COLUMNS
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'job_position' AND COLUMN_NAME = 'data_source');
SET @ddl := IF(@has_col = 0,
  'ALTER TABLE job_position ADD COLUMN data_source VARCHAR(16) NOT NULL DEFAULT ''platform'' COMMENT ''数据来源：platform平台发布 self_crawl自爬核心库 ext_ats外部扩充库'' AFTER welfare',
  'DO 0');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_idx := (SELECT COUNT(*) FROM information_schema.STATISTICS
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'job_position' AND INDEX_NAME = 'idx_job_position_source');
SET @ddl := IF(@has_idx = 0,
  'ALTER TABLE job_position ADD KEY idx_job_position_source (data_source, shelf_status, deleted)',
  'DO 0');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @has_chk := (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'job_position' AND CONSTRAINT_NAME = 'chk_job_position_source');
SET @ddl := IF(@has_chk = 0,
  'ALTER TABLE job_position ADD CONSTRAINT chk_job_position_source CHECK (data_source IN (''platform'', ''self_crawl'', ''ext_ats''))',
  'DO 0');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 回填：已导入的自爬校招职位
UPDATE job_position p JOIN ent_company c ON c.id = p.company_id
   SET p.data_source = 'self_crawl'
 WHERE c.credit_code LIKE 'REAL%' AND p.data_source <> 'self_crawl';
UPDATE job_position p JOIN ent_company c ON c.id = p.company_id
   SET p.data_source = 'ext_ats'
 WHERE c.credit_code LIKE 'EXTA%' AND p.data_source <> 'ext_ats';

SELECT data_source, COUNT(*) AS jobs FROM job_position WHERE deleted = 0 GROUP BY data_source;
