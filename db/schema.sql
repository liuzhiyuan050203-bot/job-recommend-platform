-- ============================================================
-- 高校就业推荐平台数据库 job_platform
-- 毕业设计：基于 Spark 与 RAG 的高校就业推荐平台
-- 字符集 utf8mb4，存储引擎 InnoDB，可重复执行
--
-- 本环境账号 job 仅拥有 job_platform.* 权限，没有 CREATE DATABASE。
-- 数据库须事先存在（本环境已建好），脚本直接 USE。
-- 建库语句（需管理员执行，应用账号不必再执行）：
--   CREATE DATABASE IF NOT EXISTS job_platform
--     DEFAULT CHARACTER SET utf8mb4
--     DEFAULT COLLATE utf8mb4_unicode_ci;
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

USE job_platform;

-- 按被引用关系从子表到父表删除，配合外键检查关闭，保证重复执行
DROP TABLE IF EXISTS ai_message;
DROP TABLE IF EXISTS ai_session;
DROP TABLE IF EXISTS rag_document;
DROP TABLE IF EXISTS spark_user_neighbor;
DROP TABLE IF EXISTS spark_recommend_eval;
DROP TABLE IF EXISTS spark_recommend;
DROP TABLE IF EXISTS spark_salary_predict;
DROP TABLE IF EXISTS spark_region_dist;
DROP TABLE IF EXISTS spark_tech_trend;
DROP TABLE IF EXISTS spark_salary_stat;
DROP TABLE IF EXISTS spark_task_log;
DROP TABLE IF EXISTS user_behavior_log;
DROP TABLE IF EXISTS cms_banner;
DROP TABLE IF EXISTS cms_article;
DROP TABLE IF EXISTS com_comment;
DROP TABLE IF EXISTS com_post;
DROP TABLE IF EXISTS job_interview;
DROP TABLE IF EXISTS job_application_log;
DROP TABLE IF EXISTS job_application;
DROP TABLE IF EXISTS job_favorite;
DROP TABLE IF EXISTS job_position_tag;
DROP TABLE IF EXISTS job_position;
DROP TABLE IF EXISTS stu_resume;
DROP TABLE IF EXISTS stu_skill;
DROP TABLE IF EXISTS ent_company;
DROP TABLE IF EXISTS stu_profile;
DROP TABLE IF EXISTS skill_tag;
DROP TABLE IF EXISTS job_category;
DROP TABLE IF EXISTS sys_user;

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- 账号。角色固定为三种，扩展资料放学生档案 / 企业资料
-- ------------------------------------------------------------
CREATE TABLE sys_user (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  username        VARCHAR(64)  NOT NULL COMMENT '登录用户名',
  password        VARCHAR(100) NOT NULL COMMENT '登录密码，BCrypt 哈希，兼容 Spring Security BCryptPasswordEncoder',
  role            TINYINT      NOT NULL COMMENT '角色：1学生 2企业 3管理员',
  nickname        VARCHAR(64)  NULL COMMENT '昵称或显示名',
  phone           VARCHAR(20)  NULL COMMENT '手机号',
  email           VARCHAR(128) NULL COMMENT '邮箱',
  avatar          VARCHAR(512) NULL COMMENT '头像地址',
  status          TINYINT      NOT NULL DEFAULT 0 COMMENT '账号状态：0待审核 1正常 2禁用 3已驳回',
  audit_remark    VARCHAR(255) NULL COMMENT '账号审核意见',
  audit_time      DATETIME     NULL COMMENT '账号审核时间',
  auditor_id      BIGINT       NULL COMMENT '账号审核人，关联 sys_user.id',
  last_login_time DATETIME     NULL COMMENT '最近登录时间',
  create_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted         TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_sys_user_username (username),
  KEY idx_sys_user_role_status (role, status, deleted),
  KEY idx_sys_user_phone (phone),
  KEY idx_sys_user_email (email),
  KEY idx_sys_user_auditor (auditor_id),
  CONSTRAINT fk_sys_user_auditor FOREIGN KEY (auditor_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_sys_user_role CHECK (role IN (1, 2, 3)),
  CONSTRAINT chk_sys_user_status CHECK (status IN (0, 1, 2, 3))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='统一用户账号（学生、企业、管理员）';

-- ------------------------------------------------------------
-- 职位分类。叶子分类名称与职位 tech_direction 使用同一套口径
-- ------------------------------------------------------------
CREATE TABLE job_category (
  id          BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
  parent_id   BIGINT      NULL COMMENT '父分类编号，空表示顶级分类',
  name        VARCHAR(64) NOT NULL COMMENT '分类名称',
  sort_no     INT         NOT NULL DEFAULT 0 COMMENT '排序号，小的在前',
  status      TINYINT     NOT NULL DEFAULT 1 COMMENT '启用状态：0停用 1启用',
  create_time DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted     TINYINT     NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_job_category_parent (parent_id, sort_no),
  KEY idx_job_category_name (name),
  CONSTRAINT fk_job_category_parent FOREIGN KEY (parent_id) REFERENCES job_category (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_job_category_status CHECK (status IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='职位分类';

-- ------------------------------------------------------------
-- 技能标签。direction 与职位技术方向同口径，供检索、雷达图和词云
-- ------------------------------------------------------------
CREATE TABLE skill_tag (
  id          BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
  name        VARCHAR(64) NOT NULL COMMENT '技能名称',
  direction   VARCHAR(64) NOT NULL COMMENT '所属技术方向，如后端开发、前端开发、数据开发、人工智能',
  sort_no     INT         NOT NULL DEFAULT 0 COMMENT '排序号，小的在前',
  status      TINYINT     NOT NULL DEFAULT 1 COMMENT '启用状态：0停用 1启用',
  create_time DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted     TINYINT     NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_skill_tag_name (name),
  KEY idx_skill_tag_direction (direction, status, deleted),
  CONSTRAINT chk_skill_tag_status CHECK (status IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='技能标签';

CREATE TABLE stu_profile (
  id                 BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id            BIGINT       NOT NULL COMMENT '学生用户编号，关联 sys_user.id，一人一份档案',
  real_name          VARCHAR(64)  NOT NULL COMMENT '真实姓名',
  gender             TINYINT      NOT NULL DEFAULT 0 COMMENT '性别：0未知 1男 2女',
  birthday           DATE         NULL COMMENT '出生日期',
  student_no         VARCHAR(32)  NULL COMMENT '学号',
  school             VARCHAR(128) NULL COMMENT '学校',
  college            VARCHAR(128) NULL COMMENT '学院',
  major              VARCHAR(128) NULL COMMENT '专业',
  education          TINYINT      NOT NULL COMMENT '学历：1专科 2本科 3硕士 4博士',
  graduation_year    SMALLINT     NOT NULL COMMENT '毕业年份，如 2026',
  expect_city        VARCHAR(64)  NULL COMMENT '期望工作城市',
  expect_salary_min  INT          NULL COMMENT '期望月薪下限，单位元',
  expect_salary_max  INT          NULL COMMENT '期望月薪上限，单位元',
  expect_direction   VARCHAR(64)  NULL COMMENT '期望技术方向，口径同 skill_tag.direction',
  self_intro         VARCHAR(1000) NULL COMMENT '自我介绍',
  create_time        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted            TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stu_profile_user (user_id),
  UNIQUE KEY uk_stu_profile_student_no (student_no),
  KEY idx_stu_profile_edu (education, graduation_year),
  KEY idx_stu_profile_direction (expect_direction, expect_city),
  CONSTRAINT fk_stu_profile_user FOREIGN KEY (user_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_stu_profile_gender CHECK (gender IN (0, 1, 2)),
  CONSTRAINT chk_stu_profile_edu CHECK (education IN (1, 2, 3, 4)),
  CONSTRAINT chk_stu_profile_salary CHECK (
    expect_salary_min IS NULL
    OR expect_salary_max IS NULL
    OR expect_salary_max >= expect_salary_min
  )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='学生档案';

CREATE TABLE stu_skill (
  id          BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id     BIGINT   NOT NULL COMMENT '学生用户编号，关联 sys_user.id',
  tag_id      BIGINT   NOT NULL COMMENT '技能标签编号，关联 skill_tag.id',
  proficiency TINYINT  NOT NULL COMMENT '熟练度 1到5，供学生技能雷达图',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted     TINYINT  NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stu_skill_user_tag (user_id, tag_id),
  KEY idx_stu_skill_tag (tag_id),
  CONSTRAINT fk_stu_skill_user FOREIGN KEY (user_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_stu_skill_tag FOREIGN KEY (tag_id) REFERENCES skill_tag (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_stu_skill_level CHECK (proficiency BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='学生技能及熟练度';

CREATE TABLE ent_company (
  id            BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id       BIGINT        NOT NULL COMMENT '企业登录账号，关联 sys_user.id，一个账号对应一家企业',
  company_name  VARCHAR(128)  NOT NULL COMMENT '企业全称',
  short_name    VARCHAR(64)   NULL COMMENT '企业简称',
  logo_url      VARCHAR(512)  NULL COMMENT '企业徽标地址',
  industry      VARCHAR(64)   NULL COMMENT '所属行业',
  scale         TINYINT       NOT NULL DEFAULT 0 COMMENT '人员规模：0未知 1二十人以下 2二十至九十九人 3一百至四百九十九人 4五百至九百九十九人 5一千至九千九百九十九人 6一万人以上',
  province      VARCHAR(32)   NULL COMMENT '所在省份，地图名称口径，如广东、北京',
  city          VARCHAR(32)   NULL COMMENT '所在城市',
  address       VARCHAR(255)  NULL COMMENT '详细地址',
  website       VARCHAR(255)  NULL COMMENT '企业网站',
  intro         TEXT          NULL COMMENT '企业简介',
  credit_code   VARCHAR(32)   NULL COMMENT '统一社会信用代码',
  license_url   VARCHAR(512)  NULL COMMENT '营业执照或资质证明地址',
  contact_name  VARCHAR(64)   NULL COMMENT '招聘联系人',
  contact_phone VARCHAR(20)   NULL COMMENT '招聘联系电话',
  contact_email VARCHAR(128)  NULL COMMENT '招聘联系邮箱',
  audit_status  TINYINT       NOT NULL DEFAULT 0 COMMENT '资质审核状态：0待审核 1已通过 2已驳回',
  audit_remark  VARCHAR(255)  NULL COMMENT '资质审核意见',
  audit_time    DATETIME      NULL COMMENT '资质审核时间',
  auditor_id    BIGINT        NULL COMMENT '资质审核人，关联 sys_user.id',
  create_time   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted       TINYINT       NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_ent_company_user (user_id),
  UNIQUE KEY uk_ent_company_credit (credit_code),
  KEY idx_ent_company_audit (audit_status, deleted),
  KEY idx_ent_company_city (province, city),
  KEY idx_ent_company_auditor (auditor_id),
  CONSTRAINT fk_ent_company_user FOREIGN KEY (user_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_ent_company_auditor FOREIGN KEY (auditor_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_ent_company_scale CHECK (scale BETWEEN 0 AND 6),
  CONSTRAINT chk_ent_company_audit CHECK (audit_status IN (0, 1, 2))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='企业资料与资质审核';

CREATE TABLE stu_resume (
  id               BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id          BIGINT       NOT NULL COMMENT '学生用户编号，关联 sys_user.id',
  title            VARCHAR(128) NOT NULL COMMENT '简历标题',
  is_default       TINYINT      NOT NULL DEFAULT 0 COMMENT '是否默认简历：0否 1是',
  education_exp    TEXT         NULL COMMENT '教育经历',
  project_exp      TEXT         NULL COMMENT '项目经历',
  internship_exp   TEXT         NULL COMMENT '实习经历',
  skill_desc       TEXT         NULL COMMENT '技能概述，供内容匹配',
  self_evaluation  TEXT         NULL COMMENT '自我评价',
  attachment_url   VARCHAR(512) NULL COMMENT '附件简历地址',
  create_time      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted          TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_stu_resume_user (user_id, is_default, deleted),
  CONSTRAINT fk_stu_resume_user FOREIGN KEY (user_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_stu_resume_default CHECK (is_default IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='学生在线简历';

CREATE TABLE job_position (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  company_id      BIGINT       NOT NULL COMMENT '发布企业，关联 ent_company.id',
  category_id     BIGINT       NOT NULL COMMENT '职位分类，关联 job_category.id',
  title           VARCHAR(128) NOT NULL COMMENT '职位名称',
  tech_direction  VARCHAR(64)  NOT NULL COMMENT '技术方向，检索和 Spark 聚合口径，发布时取叶子分类名称',
  province        VARCHAR(32)  NOT NULL COMMENT '工作省份，地图名称口径，如北京、广东',
  city            VARCHAR(32)  NOT NULL COMMENT '工作城市',
  district        VARCHAR(32)  NULL COMMENT '区县',
  address         VARCHAR(255) NULL COMMENT '工作地址',
  salary_min      INT          NOT NULL COMMENT '最低月薪，单位元',
  salary_max      INT          NOT NULL COMMENT '最高月薪，单位元',
  salary_months   TINYINT      NOT NULL DEFAULT 12 COMMENT '年薪发放月数，如 13 表示十三薪',
  education       TINYINT      NOT NULL DEFAULT 0 COMMENT '学历要求：0不限 1专科 2本科 3硕士 4博士',
  experience_req  TINYINT      NOT NULL DEFAULT 0 COMMENT '经验要求：0不限 1应届生 2一年以内 3一到三年 4三到五年 5五年以上',
  job_type        TINYINT      NOT NULL DEFAULT 3 COMMENT '工作性质：1全职 2实习 3校招',
  headcount       INT          NOT NULL DEFAULT 1 COMMENT '招聘人数',
  description     TEXT         NULL COMMENT '岗位职责',
  requirement     TEXT         NULL COMMENT '任职要求',
  welfare         VARCHAR(500) NULL COMMENT '福利待遇',
  shelf_status    TINYINT      NOT NULL DEFAULT 0 COMMENT '上下架状态：0下架 1上架',
  audit_status    TINYINT      NOT NULL DEFAULT 0 COMMENT '职位审核状态：0待审核 1已通过 2已驳回',
  audit_remark    VARCHAR(255) NULL COMMENT '职位审核意见',
  audit_time      DATETIME     NULL COMMENT '职位审核时间',
  auditor_id      BIGINT       NULL COMMENT '职位审核人，关联 sys_user.id',
  publish_time    DATETIME     NULL COMMENT '最近上架或刷新时间，列表按该字段倒序即为最新',
  view_count      INT          NOT NULL DEFAULT 0 COMMENT '浏览次数',
  favorite_count  INT          NOT NULL DEFAULT 0 COMMENT '收藏次数',
  apply_count     INT          NOT NULL DEFAULT 0 COMMENT '投递次数',
  create_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted         TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_job_position_company (company_id, shelf_status, deleted),
  KEY idx_job_position_category (category_id),
  KEY idx_job_position_auditor (auditor_id),
  KEY idx_job_position_list (shelf_status, audit_status, deleted, publish_time),
  KEY idx_job_position_city_dir (city, tech_direction, education),
  KEY idx_job_position_province (province, city),
  KEY idx_job_position_salary (salary_min, salary_max),
  CONSTRAINT fk_job_position_company FOREIGN KEY (company_id) REFERENCES ent_company (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_job_position_category FOREIGN KEY (category_id) REFERENCES job_category (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_job_position_auditor FOREIGN KEY (auditor_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_job_position_salary CHECK (salary_min >= 0 AND salary_max >= salary_min),
  CONSTRAINT chk_job_position_months CHECK (salary_months BETWEEN 12 AND 24),
  CONSTRAINT chk_job_position_edu CHECK (education IN (0, 1, 2, 3, 4)),
  CONSTRAINT chk_job_position_exp CHECK (experience_req IN (0, 1, 2, 3, 4, 5)),
  CONSTRAINT chk_job_position_type CHECK (job_type IN (1, 2, 3)),
  CONSTRAINT chk_job_position_headcount CHECK (headcount >= 1),
  CONSTRAINT chk_job_position_shelf CHECK (shelf_status IN (0, 1)),
  CONSTRAINT chk_job_position_audit CHECK (audit_status IN (0, 1, 2))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='招聘职位';

CREATE TABLE job_position_tag (
  id          BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
  position_id BIGINT   NOT NULL COMMENT '职位编号，关联 job_position.id',
  tag_id      BIGINT   NOT NULL COMMENT '技能标签编号，关联 skill_tag.id',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted     TINYINT  NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_job_position_tag (position_id, tag_id),
  KEY idx_job_position_tag_tag (tag_id, deleted),
  CONSTRAINT fk_job_position_tag_position FOREIGN KEY (position_id) REFERENCES job_position (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_job_position_tag_tag FOREIGN KEY (tag_id) REFERENCES skill_tag (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='职位与技能标签关联';

CREATE TABLE job_favorite (
  id          BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id     BIGINT   NOT NULL COMMENT '学生用户编号，关联 sys_user.id',
  position_id BIGINT   NOT NULL COMMENT '职位编号，关联 job_position.id',
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted     TINYINT  NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是，再次收藏时把本字段改回 0',
  PRIMARY KEY (id),
  UNIQUE KEY uk_job_favorite_user_position (user_id, position_id),
  KEY idx_job_favorite_position (position_id, deleted),
  CONSTRAINT fk_job_favorite_user FOREIGN KEY (user_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_job_favorite_position FOREIGN KEY (position_id) REFERENCES job_position (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='职位收藏';

CREATE TABLE job_application (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id     BIGINT       NOT NULL COMMENT '投递学生，关联 sys_user.id',
  position_id BIGINT       NOT NULL COMMENT '投递职位，关联 job_position.id',
  company_id  BIGINT       NOT NULL COMMENT '职位所属企业，关联 ent_company.id，写入时须与职位一致，便于企业漏斗统计',
  resume_id   BIGINT       NULL COMMENT '使用的在线简历，关联 stu_resume.id',
  status      TINYINT      NOT NULL DEFAULT 0 COMMENT '投递状态：0待初筛 1笔试 2面试中 3已录用 4未通过',
  remark      VARCHAR(500) NULL COMMENT '当前状态说明',
  apply_time  DATETIME     NOT NULL COMMENT '投递时间',
  create_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted     TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_job_application_user_position (user_id, position_id),
  KEY idx_job_application_company_status (company_id, status, deleted),
  KEY idx_job_application_position (position_id, status),
  KEY idx_job_application_resume (resume_id),
  KEY idx_job_application_user_status (user_id, status, deleted),
  CONSTRAINT fk_job_application_user FOREIGN KEY (user_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_job_application_position FOREIGN KEY (position_id) REFERENCES job_position (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_job_application_company FOREIGN KEY (company_id) REFERENCES ent_company (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_job_application_resume FOREIGN KEY (resume_id) REFERENCES stu_resume (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_job_application_status CHECK (status IN (0, 1, 2, 3, 4))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='简历投递';

CREATE TABLE job_application_log (
  id             BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  application_id BIGINT       NOT NULL COMMENT '投递编号，关联 job_application.id',
  from_status    TINYINT      NULL COMMENT '变更前状态，新建投递时为空；取值同 job_application.status',
  to_status      TINYINT      NOT NULL COMMENT '变更后状态：0待初筛 1笔试 2面试中 3已录用 4未通过',
  operator_id    BIGINT       NOT NULL COMMENT '操作人，关联 sys_user.id',
  remark         VARCHAR(500) NULL COMMENT '变更说明',
  create_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted        TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_job_app_log_application (application_id, id),
  KEY idx_job_app_log_operator (operator_id),
  CONSTRAINT fk_job_app_log_application FOREIGN KEY (application_id) REFERENCES job_application (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_job_app_log_operator FOREIGN KEY (operator_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_job_app_log_from CHECK (from_status IS NULL OR from_status IN (0, 1, 2, 3, 4)),
  CONSTRAINT chk_job_app_log_to CHECK (to_status IN (0, 1, 2, 3, 4))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='投递状态变更日志';

CREATE TABLE job_interview (
  id                    BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  application_id        BIGINT       NOT NULL COMMENT '投递编号，关联 job_application.id',
  user_id               BIGINT       NOT NULL COMMENT '面试学生，关联 sys_user.id',
  company_id            BIGINT       NOT NULL COMMENT '面试企业，关联 ent_company.id',
  position_id           BIGINT       NOT NULL COMMENT '面试职位，关联 job_position.id',
  round_no              INT          NOT NULL DEFAULT 1 COMMENT '面试轮次，从 1 开始',
  round_name            VARCHAR(64)  NOT NULL COMMENT '轮次名称，如技术一面、二面、HR面',
  interview_time        DATETIME     NOT NULL COMMENT '面试开始时间',
  interview_type        TINYINT      NOT NULL COMMENT '面试方式：1线上 2线下',
  location              VARCHAR(255) NULL COMMENT '线下面试地点',
  meeting_url           VARCHAR(512) NULL COMMENT '线上面试链接',
  contact_name          VARCHAR(64)  NULL COMMENT '面试联系人',
  contact_phone         VARCHAR(20)  NULL COMMENT '面试联系电话',
  interview_status      TINYINT      NOT NULL DEFAULT 0 COMMENT '面试状态：0待进行 1已完成 2已取消 3学生缺席',
  remind_ahead_minutes  INT          NOT NULL DEFAULT 1440 COMMENT '提前提醒分钟数，默认 1440 即一天',
  remind_status         TINYINT      NOT NULL DEFAULT 0 COMMENT '提醒状态：0未提醒 1已提醒 2无需提醒',
  remind_time           DATETIME     NULL COMMENT '实际发出提醒的时间',
  remark                VARCHAR(500) NULL COMMENT '面试备注',
  create_time           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted               TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_job_interview_application (application_id, round_no),
  KEY idx_job_interview_user_time (user_id, interview_time),
  KEY idx_job_interview_company_time (company_id, interview_time),
  KEY idx_job_interview_position (position_id),
  KEY idx_job_interview_remind (remind_status, interview_time, deleted),
  CONSTRAINT fk_job_interview_application FOREIGN KEY (application_id) REFERENCES job_application (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_job_interview_user FOREIGN KEY (user_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_job_interview_company FOREIGN KEY (company_id) REFERENCES ent_company (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_job_interview_position FOREIGN KEY (position_id) REFERENCES job_position (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_job_interview_type CHECK (interview_type IN (1, 2)),
  CONSTRAINT chk_job_interview_status CHECK (interview_status IN (0, 1, 2, 3)),
  CONSTRAINT chk_job_interview_remind CHECK (remind_status IN (0, 1, 2)),
  CONSTRAINT chk_job_interview_round CHECK (round_no >= 1),
  CONSTRAINT chk_job_interview_ahead CHECK (remind_ahead_minutes >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='面试日程与提醒';

CREATE TABLE com_post (
  id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id      BIGINT       NOT NULL COMMENT '作者，关联 sys_user.id',
  company_id   BIGINT       NULL COMMENT '相关企业，关联 ent_company.id，可空',
  position_id  BIGINT       NULL COMMENT '相关职位，关联 job_position.id，可空',
  post_type    TINYINT      NOT NULL COMMENT '帖子类型：1面经 2企业评价',
  title        VARCHAR(128) NOT NULL COMMENT '标题',
  content      TEXT         NOT NULL COMMENT '正文',
  rating       TINYINT      NULL COMMENT '评分 1到5，企业评价使用，面经可空',
  audit_status TINYINT      NOT NULL DEFAULT 0 COMMENT '审核状态：0待审核 1已通过 2已驳回',
  audit_remark VARCHAR(255) NULL COMMENT '审核意见',
  audit_time   DATETIME     NULL COMMENT '审核时间',
  auditor_id   BIGINT       NULL COMMENT '审核人，关联 sys_user.id',
  like_count   INT          NOT NULL DEFAULT 0 COMMENT '点赞数',
  create_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted      TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_com_post_audit (audit_status, post_type, create_time),
  KEY idx_com_post_user (user_id, deleted),
  KEY idx_com_post_company (company_id, audit_status),
  KEY idx_com_post_position (position_id),
  KEY idx_com_post_auditor (auditor_id),
  CONSTRAINT fk_com_post_user FOREIGN KEY (user_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_com_post_company FOREIGN KEY (company_id) REFERENCES ent_company (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_com_post_position FOREIGN KEY (position_id) REFERENCES job_position (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_com_post_auditor FOREIGN KEY (auditor_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_com_post_type CHECK (post_type IN (1, 2)),
  CONSTRAINT chk_com_post_rating CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
  CONSTRAINT chk_com_post_audit CHECK (audit_status IN (0, 1, 2))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='面经与企业评价';

CREATE TABLE com_comment (
  id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  post_id      BIGINT       NOT NULL COMMENT '所属帖子，关联 com_post.id',
  user_id      BIGINT       NOT NULL COMMENT '评论人，关联 sys_user.id',
  content      VARCHAR(1000) NOT NULL COMMENT '评论内容',
  audit_status TINYINT      NOT NULL DEFAULT 0 COMMENT '审核状态：0待审核 1已通过 2已驳回',
  audit_remark VARCHAR(255) NULL COMMENT '审核意见',
  audit_time   DATETIME     NULL COMMENT '审核时间',
  auditor_id   BIGINT       NULL COMMENT '审核人，关联 sys_user.id',
  create_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted      TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_com_comment_post (post_id, audit_status, deleted),
  KEY idx_com_comment_audit (audit_status, create_time),
  KEY idx_com_comment_user (user_id),
  KEY idx_com_comment_auditor (auditor_id),
  CONSTRAINT fk_com_comment_post FOREIGN KEY (post_id) REFERENCES com_post (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_com_comment_user FOREIGN KEY (user_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_com_comment_auditor FOREIGN KEY (auditor_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_com_comment_audit CHECK (audit_status IN (0, 1, 2))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='社区评论';

CREATE TABLE cms_article (
  id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  article_type TINYINT      NOT NULL COMMENT '内容类型：1双选会公告 2就业政策 3新闻资讯',
  title        VARCHAR(128) NOT NULL COMMENT '标题',
  cover_url    VARCHAR(512) NULL COMMENT '封面图地址',
  summary      VARCHAR(500) NULL COMMENT '摘要',
  content      MEDIUMTEXT   NOT NULL COMMENT '正文',
  publisher_id BIGINT       NOT NULL COMMENT '发布人，关联 sys_user.id',
  publish_time DATETIME     NULL COMMENT '发布时间',
  top_flag     TINYINT      NOT NULL DEFAULT 0 COMMENT '是否置顶：0否 1是',
  status       TINYINT      NOT NULL DEFAULT 0 COMMENT '发布状态：0草稿 1已发布 2已下线',
  view_count   INT          NOT NULL DEFAULT 0 COMMENT '浏览次数',
  create_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted      TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_cms_article_list (article_type, status, deleted, publish_time),
  KEY idx_cms_article_publisher (publisher_id),
  CONSTRAINT fk_cms_article_publisher FOREIGN KEY (publisher_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_cms_article_type CHECK (article_type IN (1, 2, 3)),
  CONSTRAINT chk_cms_article_status CHECK (status IN (0, 1, 2)),
  CONSTRAINT chk_cms_article_top CHECK (top_flag IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='公告、新闻与就业政策';

CREATE TABLE cms_banner (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  title       VARCHAR(128) NOT NULL COMMENT '轮播标题',
  image_url   VARCHAR(512) NOT NULL COMMENT '图片地址',
  link_url    VARCHAR(512) NULL COMMENT '点击跳转地址',
  sort_no     INT          NOT NULL DEFAULT 0 COMMENT '排序号，小的在前',
  status      TINYINT      NOT NULL DEFAULT 1 COMMENT '启用状态：0停用 1启用',
  start_time  DATETIME     NULL COMMENT '投放开始时间，空表示不限制',
  end_time    DATETIME     NULL COMMENT '投放结束时间，空表示不限制',
  create_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted     TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_cms_banner_show (status, deleted, sort_no),
  CONSTRAINT chk_cms_banner_status CHECK (status IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='首页轮播图';

-- 行为日志不建物理外键：写入频繁，User-CF 按时间窗扫描，职位下架后历史行为仍要保留
CREATE TABLE user_behavior_log (
  id            BIGINT   NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id       BIGINT   NOT NULL COMMENT '行为用户，逻辑关联 sys_user.id',
  behavior_type TINYINT  NOT NULL COMMENT '行为类型：1浏览 2收藏 3投递',
  target_type   TINYINT  NOT NULL DEFAULT 1 COMMENT '对象类型：1职位',
  target_id     BIGINT   NOT NULL COMMENT '对象编号，target_type=1 时逻辑关联 job_position.id',
  weight        INT      NOT NULL COMMENT '隐式反馈权重，建议浏览1、收藏3、投递5，供 User-CF',
  create_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted       TINYINT  NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是，脏数据可剔除且不参与训练',
  PRIMARY KEY (id),
  KEY idx_behavior_user_cf (user_id, behavior_type, target_id),
  KEY idx_behavior_item (target_type, target_id, behavior_type),
  KEY idx_behavior_time (create_time),
  CONSTRAINT chk_behavior_type CHECK (behavior_type IN (1, 2, 3)),
  CONSTRAINT chk_behavior_weight CHECK (weight > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户行为日志（浏览、收藏、投递）';

-- Spark 结果与任务日志不建物理外键。批次覆盖写入频繁，
-- 且历史推荐需要在职位下架或逻辑删除后仍然可读。
CREATE TABLE spark_task_log (
  id           BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  batch_no     VARCHAR(32)  NOT NULL COMMENT '批次号，同一轮离线任务共用，结果表通过该字段逻辑关联',
  task_code    VARCHAR(32)  NOT NULL COMMENT '任务编码：clean清洗 aggregate聚合 salary_regression薪资回归 recommend混合推荐 user_cf协同过滤 content_match内容匹配',
  task_name    VARCHAR(64)  NOT NULL COMMENT '任务名称',
  status       TINYINT      NOT NULL COMMENT '执行状态：0运行中 1成功 2失败',
  start_time   DATETIME     NOT NULL COMMENT '开始时间',
  end_time     DATETIME     NULL COMMENT '结束时间',
  input_count  BIGINT       NULL COMMENT '输入行数',
  output_count BIGINT       NULL COMMENT '输出行数',
  result_msg   VARCHAR(500) NULL COMMENT '成功时的结果摘要',
  error_msg    TEXT         NULL COMMENT '失败时的错误信息',
  params_json  JSON         NULL COMMENT '任务参数',
  create_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted      TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_spark_task_batch (batch_no, task_code),
  KEY idx_spark_task_status (status, start_time),
  CONSTRAINT chk_spark_task_status CHECK (status IN (0, 1, 2))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Spark任务执行日志';

CREATE TABLE spark_salary_stat (
  id             BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  batch_no       VARCHAR(32)   NOT NULL COMMENT '批次号，逻辑关联 spark_task_log.batch_no',
  province       VARCHAR(32)   NOT NULL COMMENT '省份，地图名称口径',
  city           VARCHAR(32)   NOT NULL COMMENT '城市',
  tech_direction VARCHAR(64)   NOT NULL COMMENT '技术方向',
  job_count      INT           NOT NULL COMMENT '样本量，职位数',
  avg_salary     DECIMAL(12,2) NOT NULL COMMENT '平均月薪，单位元',
  median_salary  DECIMAL(12,2) NOT NULL COMMENT '月薪中位数，单位元',
  min_salary     DECIMAL(12,2) NOT NULL COMMENT '最低月薪，单位元',
  max_salary     DECIMAL(12,2) NOT NULL COMMENT '最高月薪，单位元',
  p25_salary     DECIMAL(12,2) NULL COMMENT '月薪第25百分位，单位元',
  p75_salary     DECIMAL(12,2) NULL COMMENT '月薪第75百分位，单位元',
  is_latest      TINYINT       NOT NULL DEFAULT 1 COMMENT '是否当前生效批次：0否 1是，查询图表时过滤 1',
  create_time    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted        TINYINT       NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_spark_salary_stat (batch_no, province, city, tech_direction),
  KEY idx_spark_salary_latest (is_latest, deleted, city, tech_direction),
  CONSTRAINT chk_spark_salary_latest CHECK (is_latest IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='按城市与技术方向的薪资统计';

CREATE TABLE spark_tech_trend (
  id             BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  batch_no       VARCHAR(32)   NOT NULL COMMENT '批次号，逻辑关联 spark_task_log.batch_no',
  stat_month     CHAR(7)       NOT NULL COMMENT '统计月份，格式 YYYY-MM',
  tag_name       VARCHAR(64)   NOT NULL COMMENT '技能或技术名称',
  tech_direction VARCHAR(64)   NOT NULL COMMENT '技术方向',
  demand_count   INT           NOT NULL COMMENT '需求量，该月出现该技术的职位数',
  avg_salary     DECIMAL(12,2) NULL COMMENT '该技术相关职位平均月薪，单位元',
  mom_rate       DECIMAL(8,4)  NULL COMMENT '需求量环比增长率，0.1000 表示增长 10%，首月为空',
  is_latest      TINYINT       NOT NULL DEFAULT 1 COMMENT '是否当前生效批次：0否 1是',
  create_time    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted        TINYINT       NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_spark_tech_trend (batch_no, stat_month, tag_name),
  KEY idx_spark_trend_latest (is_latest, deleted, stat_month, tech_direction),
  CONSTRAINT chk_spark_trend_latest CHECK (is_latest IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='技术需求趋势';

CREATE TABLE spark_region_dist (
  id            BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  batch_no      VARCHAR(32)   NOT NULL COMMENT '批次号，逻辑关联 spark_task_log.batch_no',
  province_name VARCHAR(32)   NOT NULL COMMENT '省份名称，与 ECharts 中国地图一致，如北京、广东',
  adcode        CHAR(6)       NOT NULL COMMENT '行政区划代码，如 110000、440000',
  job_count     INT           NOT NULL COMMENT '职位数',
  company_count INT           NOT NULL COMMENT '企业数',
  avg_salary    DECIMAL(12,2) NULL COMMENT '平均月薪，单位元',
  apply_count   INT           NOT NULL DEFAULT 0 COMMENT '投递数',
  is_latest     TINYINT       NOT NULL DEFAULT 1 COMMENT '是否当前生效批次：0否 1是',
  create_time   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted       TINYINT       NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_spark_region_dist (batch_no, adcode),
  KEY idx_spark_region_latest (is_latest, deleted, province_name),
  CONSTRAINT chk_spark_region_latest CHECK (is_latest IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='就业地区分布（中国热力图）';

CREATE TABLE spark_salary_predict (
  id               BIGINT        NOT NULL AUTO_INCREMENT COMMENT '主键',
  batch_no         VARCHAR(32)   NOT NULL COMMENT '批次号，逻辑关联 spark_task_log.batch_no',
  user_id          BIGINT        NULL COMMENT '学生用户编号，逻辑关联 sys_user.id，岗位样本预测时可空',
  position_id      BIGINT        NULL COMMENT '职位编号，逻辑关联 job_position.id，可空',
  province         VARCHAR(32)   NOT NULL COMMENT '省份',
  city             VARCHAR(32)   NOT NULL COMMENT '城市',
  tech_direction   VARCHAR(64)   NOT NULL COMMENT '技术方向',
  education        TINYINT       NOT NULL COMMENT '学历：1专科 2本科 3硕士 4博士',
  experience_years DECIMAL(4,1)  NOT NULL DEFAULT 0.0 COMMENT '工作年限，应届为 0',
  predicted_salary DECIMAL(12,2) NOT NULL COMMENT '预测月薪，单位元',
  ci_low           DECIMAL(12,2) NULL COMMENT '预测区间下限，单位元',
  ci_high          DECIMAL(12,2) NULL COMMENT '预测区间上限，单位元',
  model_version    VARCHAR(32)   NOT NULL COMMENT '回归模型版本',
  feature_json     JSON          NULL COMMENT '回归特征向量',
  is_latest        TINYINT       NOT NULL DEFAULT 1 COMMENT '是否当前生效批次：0否 1是',
  create_time      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted          TINYINT       NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_spark_predict_latest (is_latest, deleted, city, tech_direction, education),
  KEY idx_spark_predict_user (user_id, is_latest),
  KEY idx_spark_predict_position (position_id, is_latest),
  KEY idx_spark_predict_batch (batch_no),
  CONSTRAINT chk_spark_predict_edu CHECK (education IN (1, 2, 3, 4)),
  CONSTRAINT chk_spark_predict_latest CHECK (is_latest IN (0, 1)),
  CONSTRAINT chk_spark_predict_exp CHECK (experience_years >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='薪资回归预测结果';

CREATE TABLE spark_recommend (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  batch_no      VARCHAR(32)  NOT NULL COMMENT '批次号，逻辑关联 spark_task_log.batch_no',
  user_id       BIGINT       NOT NULL COMMENT '被推荐学生，逻辑关联 sys_user.id',
  position_id   BIGINT       NOT NULL COMMENT '推荐职位，逻辑关联 job_position.id',
  algo          TINYINT      NOT NULL COMMENT '算法：1User-CF协同过滤 2内容匹配 3融合',
  match_score   DECIMAL(6,2) NOT NULL COMMENT '匹配分，0到100，列表按该分排序',
  cf_score      DECIMAL(6,2) NULL COMMENT '协同过滤分，0到100，非该算法时可空',
  content_score DECIMAL(6,2) NULL COMMENT '内容匹配分，0到100，非该算法时可空',
  rank_no       INT          NOT NULL COMMENT '推荐名次，从 1 开始，同一用户同一批次内排序',
  reason        VARCHAR(255) NULL COMMENT '推荐理由摘要',
  is_latest     TINYINT      NOT NULL DEFAULT 1 COMMENT '是否当前生效批次：0否 1是',
  create_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted       TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_spark_recommend (batch_no, user_id, position_id, algo),
  KEY idx_spark_recommend_user (user_id, is_latest, deleted, rank_no),
  KEY idx_spark_recommend_position (position_id, is_latest),
  CONSTRAINT chk_spark_recommend_algo CHECK (algo IN (1, 2, 3)),
  CONSTRAINT chk_spark_recommend_score CHECK (match_score >= 0 AND match_score <= 100),
  CONSTRAINT chk_spark_recommend_cf CHECK (cf_score IS NULL OR (cf_score >= 0 AND cf_score <= 100)),
  CONSTRAINT chk_spark_recommend_content CHECK (content_score IS NULL OR (content_score >= 0 AND content_score <= 100)),
  CONSTRAINT chk_spark_recommend_rank CHECK (rank_no >= 1),
  CONSTRAINT chk_spark_recommend_latest CHECK (is_latest IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='职位推荐结果';

-- 离线评估不建物理外键，随推荐批次切换 is_latest，只保留最近若干批
CREATE TABLE spark_recommend_eval (
  id             BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  batch_no       VARCHAR(32)  NOT NULL COMMENT '批次号，逻辑关联 spark_task_log.batch_no',
  algo           VARCHAR(16)  NOT NULL COMMENT '算法：cf协同过滤 content内容 hybrid融合 popular热门基线',
  k              INT          NOT NULL COMMENT '截断名次 K',
  precision_at_k DECIMAL(8,4) NOT NULL COMMENT 'Precision@K，0到1',
  recall_at_k    DECIMAL(8,4) NOT NULL COMMENT 'Recall@K，0到1',
  ndcg_at_k      DECIMAL(8,4) NOT NULL COMMENT 'NDCG@K，0到1',
  coverage       DECIMAL(8,4) NOT NULL COMMENT '目录覆盖率，Top-K去重职位数/候选职位数，0到1',
  user_count     INT          NOT NULL COMMENT '参与评估的学生数',
  alpha          DECIMAL(6,4) NULL COMMENT '融合权重，仅 hybrid 有值，其余为空',
  cf_method      VARCHAR(16)  NULL COMMENT '协同过滤实现：user_cosine用户余弦 als隐式ALS',
  is_latest      TINYINT      NOT NULL DEFAULT 1 COMMENT '是否当前生效批次：0否 1是',
  create_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted        TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  UNIQUE KEY uk_spark_recommend_eval (batch_no, algo, k),
  KEY idx_spark_recommend_eval_latest (is_latest, deleted, algo, k),
  CONSTRAINT chk_spark_recommend_eval_k CHECK (k >= 1),
  CONSTRAINT chk_spark_recommend_eval_latest CHECK (is_latest IN (0, 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='职位推荐离线评估';

-- Spark 离线计算的用户近邻。实时推荐读取 is_latest=1 的邻居，不再重算相似度
CREATE TABLE spark_user_neighbor (
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

-- 知识文档保存原文切片。向量存放在 Chroma，本表只保留 chroma_id 以便回查。
-- 同一逻辑文档的切片共用 doc_key（如 kb:就业政策.md、cms:12、job:345）。
-- 重索引时按 doc_key 物理删除旧切片，不保留逻辑删除行。
CREATE TABLE rag_document (
  id                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  doc_type          TINYINT      NOT NULL COMMENT '文档类型：1就业政策 2平台使用指南 3面经精选 4企业招聘须知 5求职指导 6手续FAQ 7职位信息',
  title             VARCHAR(128) NOT NULL COMMENT '文档标题',
  doc_key           VARCHAR(128) NULL COMMENT '逻辑文档键，同一文档的切片共用，如 kb:就业政策.md、cms:12、job:345',
  source_type       TINYINT      NOT NULL DEFAULT 1 COMMENT '来源：1手工录入 2公告同步 3政策同步 4知识库文件 5职位同步 6管理员上传',
  source_id         BIGINT       NULL COMMENT '来源业务编号。公告或政策逻辑关联 cms_article.id，职位逻辑关联 job_position.id',
  chunk_no          INT          NOT NULL DEFAULT 0 COMMENT '切片序号，从 0 开始',
  section           VARCHAR(128) NULL COMMENT '所在章节标题，无章节时为空',
  content           MEDIUMTEXT   NOT NULL COMMENT '切片正文，作为检索回显文本',
  content_hash      CHAR(64)     NULL COMMENT '标题、章节与正文的 SHA-256，十六进制，用于判断切片是否变化',
  chroma_collection VARCHAR(64)  NULL COMMENT 'Chroma 集合名',
  chroma_id         VARCHAR(64)  NULL COMMENT 'Chroma 向量编号，未入库时为空',
  embed_status      TINYINT      NOT NULL DEFAULT 0 COMMENT '向量化状态：0待处理 1已入库 2失败',
  create_time       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted           TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_rag_doc_status (doc_type, embed_status, deleted),
  KEY idx_rag_doc_source (source_type, source_id),
  KEY idx_rag_doc_hash (content_hash),
  KEY idx_rag_doc_chroma (chroma_collection, chroma_id),
  KEY idx_rag_doc_key (doc_key, deleted),
  CONSTRAINT chk_rag_doc_type CHECK (doc_type IN (1, 2, 3, 4, 5, 6, 7)),
  CONSTRAINT chk_rag_doc_source CHECK (source_type IN (1, 2, 3, 4, 5, 6)),
  CONSTRAINT chk_rag_doc_embed CHECK (embed_status IN (0, 1, 2)),
  CONSTRAINT chk_rag_doc_chunk CHECK (chunk_no >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='RAG知识文档';

CREATE TABLE ai_session (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id     BIGINT       NOT NULL COMMENT '会话所属用户，关联 sys_user.id',
  agent_type  TINYINT      NOT NULL COMMENT '智能体：1学生 2企业 3管理员',
  title       VARCHAR(128) NOT NULL COMMENT '会话标题',
  create_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted     TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_ai_session_user (user_id, agent_type, deleted, update_time),
  CONSTRAINT fk_ai_session_user FOREIGN KEY (user_id) REFERENCES sys_user (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_ai_session_agent CHECK (agent_type IN (1, 2, 3))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI会话';

CREATE TABLE ai_message (
  id          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  session_id  BIGINT       NOT NULL COMMENT '会话编号，关联 ai_session.id',
  msg_role    VARCHAR(16)  NOT NULL COMMENT '消息角色：user用户 assistant助手 system系统',
  content     MEDIUMTEXT   NOT NULL COMMENT '消息正文，助手消息为 SSE 结束后的完整文本',
  extra       TEXT         NULL COMMENT '助手附带信息，JSON 文本，含 sources、tools、latency_ms、first_token_ms',
  token_count INT          NULL COMMENT '估算 token 数，可空',
  create_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted     TINYINT      NOT NULL DEFAULT 0 COMMENT '逻辑删除：0否 1是',
  PRIMARY KEY (id),
  KEY idx_ai_message_session (session_id, id),
  CONSTRAINT fk_ai_message_session FOREIGN KEY (session_id) REFERENCES ai_session (id)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_ai_message_role CHECK (msg_role IN ('user', 'assistant', 'system'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI会话消息';
