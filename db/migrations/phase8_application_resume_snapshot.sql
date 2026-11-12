-- 投递时保存简历快照：企业查看投递当时的内容；学生之后修改只提示「投递后简历已更新」。
-- 可重复执行，不删数据。用法：
--   /opt/mysql/bin/mysql --no-defaults -h127.0.0.1 -P3307 -u"$DB_USER" -p"$DB_PASSWORD" job_platform < db/migrations/phase8_application_resume_snapshot.sql
-- 请用包装脚本从 .env 读取账号，不要在命令行或日志中打印密码。

SET NAMES utf8mb4;

SET @has_tbl := (SELECT COUNT(*) FROM information_schema.TABLES
                 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'job_application_resume');
SET @ddl := IF(@has_tbl = 0,
  'CREATE TABLE job_application_resume (
     id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT ''主键'',
     application_id  BIGINT       NOT NULL COMMENT ''投递编号，关联 job_application.id'',
     resume_id       BIGINT       NULL COMMENT ''投递时使用的在线简历编号，关联 stu_resume.id'',
     title           VARCHAR(128) NOT NULL DEFAULT '''' COMMENT ''投递时的简历标题'',
     education_exp   TEXT         NULL COMMENT ''投递时的教育经历'',
     project_exp     TEXT         NULL COMMENT ''投递时的项目经历'',
     internship_exp  TEXT         NULL COMMENT ''投递时的实习经历'',
     skill_desc      TEXT         NULL COMMENT ''投递时的技能概述'',
     self_evaluation TEXT         NULL COMMENT ''投递时的自我评价'',
     attachment_url  VARCHAR(512) NULL COMMENT ''投递时的附件地址'',
     content_hash    CHAR(64)     NOT NULL DEFAULT '''' COMMENT ''内容 SHA-256，用于判断投递后是否被修改'',
     captured_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT ''快照写入时间'',
     PRIMARY KEY (id),
     UNIQUE KEY uk_app_resume_application (application_id),
     KEY idx_app_resume_resume (resume_id),
     CONSTRAINT fk_app_resume_application FOREIGN KEY (application_id) REFERENCES job_application (id)
       ON DELETE CASCADE ON UPDATE RESTRICT
   ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT=''投递时的简历快照，企业查看以此为准''',
  'DO 0');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 回填：已有投递用当前在线简历（含逻辑删除）生成快照，已有快照的不覆盖
INSERT INTO job_application_resume (
    application_id, resume_id, title, education_exp, project_exp, internship_exp,
    skill_desc, self_evaluation, attachment_url, content_hash, captured_at
)
SELECT a.id,
       r.id,
       IFNULL(r.title, ''),
       r.education_exp,
       r.project_exp,
       r.internship_exp,
       r.skill_desc,
       r.self_evaluation,
       r.attachment_url,
       SHA2(CONCAT_WS(CHAR(1),
            IFNULL(r.title, ''),
            IFNULL(r.education_exp, ''),
            IFNULL(r.project_exp, ''),
            IFNULL(r.internship_exp, ''),
            IFNULL(r.skill_desc, ''),
            IFNULL(r.self_evaluation, ''),
            IFNULL(r.attachment_url, '')), 256),
       IFNULL(a.apply_time, NOW())
  FROM job_application a
  INNER JOIN stu_resume r ON r.id = a.resume_id
  LEFT JOIN job_application_resume s ON s.application_id = a.id
 WHERE s.application_id IS NULL;

SELECT COUNT(*) AS snapshot_rows FROM job_application_resume;
