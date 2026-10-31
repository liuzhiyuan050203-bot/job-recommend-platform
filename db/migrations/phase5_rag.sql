-- 阶段五 RAG：扩展 rag_document 类型，并增加 doc_key / section。
-- 可重复执行。不删除已有切片，不改 seed 插入列。
-- 用法：mariadb -h127.0.0.1 -ujob -pjob123 job_platform < db/migrations/phase5_rag.sql

SET NAMES utf8mb4;

-- doc_key
SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'rag_document' AND COLUMN_NAME = 'doc_key'
);
SET @sql := IF(
  @exists = 0,
  'ALTER TABLE rag_document ADD COLUMN doc_key VARCHAR(128) NULL COMMENT ''逻辑文档键，同一文档的切片共用，如 kb:就业政策.md、cms:12、job:345'' AFTER title',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- section
SET @exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'rag_document' AND COLUMN_NAME = 'section'
);
SET @sql := IF(
  @exists = 0,
  'ALTER TABLE rag_document ADD COLUMN section VARCHAR(128) NULL COMMENT ''所在章节标题，无章节时为空'' AFTER chunk_no',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 索引
SET @exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'rag_document' AND INDEX_NAME = 'idx_rag_doc_key'
);
SET @sql := IF(
  @exists = 0,
  'ALTER TABLE rag_document ADD KEY idx_rag_doc_key (doc_key, deleted)',
  'DO 0'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

ALTER TABLE rag_document DROP CONSTRAINT IF EXISTS chk_rag_doc_type;
ALTER TABLE rag_document ADD CONSTRAINT chk_rag_doc_type CHECK (doc_type IN (1, 2, 3, 4, 5, 6, 7));

ALTER TABLE rag_document DROP CONSTRAINT IF EXISTS chk_rag_doc_source;
ALTER TABLE rag_document ADD CONSTRAINT chk_rag_doc_source CHECK (source_type IN (1, 2, 3, 4, 5, 6));

UPDATE rag_document
SET doc_key = CONCAT('legacy:', id)
WHERE doc_key IS NULL OR doc_key = '';

-- 已有库的列注释仍是阶段四原文，与 schema.sql 对齐
ALTER TABLE rag_document
  MODIFY COLUMN doc_type TINYINT NOT NULL COMMENT '文档类型：1就业政策 2平台使用指南 3面经精选 4企业招聘须知 5求职指导 6手续FAQ 7职位信息',
  MODIFY COLUMN source_type TINYINT NOT NULL DEFAULT 1 COMMENT '来源：1手工录入 2公告同步 3政策同步 4知识库文件 5职位同步 6管理员上传',
  MODIFY COLUMN source_id BIGINT NULL COMMENT '来源业务编号。公告或政策逻辑关联 cms_article.id，职位逻辑关联 job_position.id',
  MODIFY COLUMN content_hash CHAR(64) NULL COMMENT '标题、章节与正文的 SHA-256，十六进制，用于判断切片是否变化';
