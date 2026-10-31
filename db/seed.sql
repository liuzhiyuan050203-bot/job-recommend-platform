-- ============================================================
-- 演示数据。先执行 schema.sql，本脚本也可单独重复执行。
-- 明文密码（库内仅存 BCrypt，兼容 Spring Security BCryptPasswordEncoder）：
--   admin   / admin123
--   student / student123
--   company / company123
-- Spark 统计行是联调占位，正式结果由 PySpark 按批次覆盖。
-- ============================================================

SET NAMES utf8mb4;
USE job_platform;

START TRANSACTION;

UPDATE job_category SET parent_id = NULL;
UPDATE sys_user SET auditor_id = NULL;

DELETE FROM ai_message;
DELETE FROM ai_session;
DELETE FROM rag_document;
DELETE FROM spark_recommend_eval;
DELETE FROM spark_recommend;
DELETE FROM spark_salary_predict;
DELETE FROM spark_region_dist;
DELETE FROM spark_tech_trend;
DELETE FROM spark_salary_stat;
DELETE FROM spark_task_log;
DELETE FROM user_behavior_log;
DELETE FROM cms_banner;
DELETE FROM cms_article;
DELETE FROM com_comment;
DELETE FROM com_post;
DELETE FROM job_interview;
DELETE FROM job_application_log;
DELETE FROM job_application;
DELETE FROM job_favorite;
DELETE FROM job_position_tag;
DELETE FROM job_position;
DELETE FROM stu_resume;
DELETE FROM stu_skill;
DELETE FROM ent_company;
DELETE FROM stu_profile;
DELETE FROM skill_tag;
DELETE FROM job_category;
DELETE FROM sys_user;

-- 明文 admin123
INSERT INTO sys_user (
  id, username, password, role, nickname, phone, email, avatar,
  status, audit_remark, audit_time, auditor_id, last_login_time,
  create_time, update_time, deleted
) VALUES (
  1, 'admin', '$2a$10$Ow2FZi2nIIc2Q1d/V7fB/OmkOi2uxBnWEzS/nhPTYhwG218GzwRHG',
  3, '系统管理员', '13800000001', 'admin@job.example', NULL,
  1, '系统初始化账号', '2026-10-01 09:00:00', NULL, '2026-10-30 08:30:00',
  '2026-10-01 09:00:00', '2026-10-30 08:30:00', 0
);

-- 明文 student123
INSERT INTO sys_user (
  id, username, password, role, nickname, phone, email, avatar,
  status, audit_remark, audit_time, auditor_id, last_login_time,
  create_time, update_time, deleted
) VALUES (
  2, 'student', '$2a$10$pmvAWsSBlmZWFXwwt3J6.ef74MTPb5XliLmkoWLJsryVeVAfmgx6a',
  1, '陈晓', '13800000002', 'chenxiao@job.example', NULL,
  1, '账号审核通过', '2026-10-08 10:00:00', 1, '2026-10-29 20:15:00',
  '2026-10-08 09:30:00', '2026-10-29 20:15:00', 0
);

-- 明文 company123
INSERT INTO sys_user (
  id, username, password, role, nickname, phone, email, avatar,
  status, audit_remark, audit_time, auditor_id, last_login_time,
  create_time, update_time, deleted
) VALUES (
  3, 'company', '$2a$10$rSonxlxZsflRtUBBia3DWeWXBDkvS6nRyacwTF2xiEou/sJ5F.nr.',
  2, '星澜招聘', '13800000003', 'hr@xinglan.example', NULL,
  1, '账号审核通过', '2026-10-08 11:00:00', 1, '2026-10-28 09:10:00',
  '2026-10-08 10:20:00', '2026-10-28 09:10:00', 0
);

INSERT INTO job_category (
  id, parent_id, name, sort_no, status, create_time, update_time, deleted
) VALUES (
  1, NULL, '技术研发', 1, 1, '2026-10-01 09:10:00', '2026-10-01 09:10:00', 0
);

INSERT INTO job_category (
  id, parent_id, name, sort_no, status, create_time, update_time, deleted
) VALUES
  (2, 1, '后端开发', 1, 1, '2026-10-01 09:11:00', '2026-10-01 09:11:00', 0),
  (3, 1, '前端开发', 2, 1, '2026-10-01 09:11:00', '2026-10-01 09:11:00', 0),
  (4, 1, '数据开发', 3, 1, '2026-10-01 09:11:00', '2026-10-01 09:11:00', 0),
  (5, 1, '人工智能', 4, 1, '2026-10-01 09:11:00', '2026-10-01 09:11:00', 0);

INSERT INTO skill_tag (
  id, name, direction, sort_no, status, create_time, update_time, deleted
) VALUES
  (1,  'Java',        '后端开发', 1,  1, '2026-10-01 09:20:00', '2026-10-01 09:20:00', 0),
  (2,  'Spring Boot', '后端开发', 2,  1, '2026-10-01 09:20:00', '2026-10-01 09:20:00', 0),
  (3,  'MySQL',       '后端开发', 3,  1, '2026-10-01 09:20:00', '2026-10-01 09:20:00', 0),
  (4,  'Redis',       '后端开发', 4,  1, '2026-10-01 09:20:00', '2026-10-01 09:20:00', 0),
  (5,  'Vue',         '前端开发', 5,  1, '2026-10-01 09:20:00', '2026-10-01 09:20:00', 0),
  (6,  'Python',      '数据开发', 6,  1, '2026-10-01 09:20:00', '2026-10-01 09:20:00', 0),
  (7,  'Spark',       '数据开发', 7,  1, '2026-10-01 09:20:00', '2026-10-01 09:20:00', 0),
  (8,  'Flink',       '数据开发', 8,  1, '2026-10-01 09:20:00', '2026-10-01 09:20:00', 0),
  (9,  'Hadoop',      '数据开发', 9,  1, '2026-10-01 09:20:00', '2026-10-01 09:20:00', 0),
  (10, 'Docker',      '后端开发', 10, 1, '2026-10-01 09:20:00', '2026-10-01 09:20:00', 0),
  (11, 'LangChain',   '人工智能', 11, 1, '2026-10-01 09:20:00', '2026-10-01 09:20:00', 0),
  (12, '机器学习',    '人工智能', 12, 1, '2026-10-01 09:20:00', '2026-10-01 09:20:00', 0);

INSERT INTO stu_profile (
  id, user_id, real_name, gender, birthday, student_no, school, college, major,
  education, graduation_year, expect_city, expect_salary_min, expect_salary_max,
  expect_direction, self_intro, create_time, update_time, deleted
) VALUES (
  1, 2, '陈晓', 1, '2004-05-16', '2022001001', '滨海理工大学', '计算机学院', '计算机科学与技术',
  2, 2026, '北京', 12000, 22000,
  '后端开发', '熟悉 Java 与 Python，做过课程项目的接口和数据处理，正在找 2026 届校招。',
  '2026-10-08 09:40:00', '2026-10-20 18:00:00', 0
);

INSERT INTO stu_skill (
  id, user_id, tag_id, proficiency, create_time, update_time, deleted
) VALUES
  (1, 2, 1, 4, '2026-10-08 09:45:00', '2026-10-08 09:45:00', 0),
  (2, 2, 2, 4, '2026-10-08 09:45:00', '2026-10-08 09:45:00', 0),
  (3, 2, 3, 4, '2026-10-08 09:45:00', '2026-10-08 09:45:00', 0),
  (4, 2, 6, 5, '2026-10-08 09:45:00', '2026-10-08 09:45:00', 0),
  (5, 2, 7, 3, '2026-10-08 09:45:00', '2026-10-08 09:45:00', 0),
  (6, 2, 5, 3, '2026-10-08 09:45:00', '2026-10-08 09:45:00', 0);

INSERT INTO ent_company (
  id, user_id, company_name, short_name, logo_url, industry, scale,
  province, city, address, website, intro, credit_code, license_url,
  contact_name, contact_phone, contact_email,
  audit_status, audit_remark, audit_time, auditor_id,
  create_time, update_time, deleted
) VALUES (
  1, 3, '星澜科技有限公司', '星澜科技', '/upload/logo/xinglan.png', '互联网', 4,
  '广东', '深圳', '南山区科技园示例路88号', 'https://www.xinglan.example',
  '星澜科技是一家面向企业数字化的演示公司，校招覆盖后端与数据开发岗位。',
  '91440300MA5D3H2X1A', '/upload/license/xinglan.png',
  '周宁', '13800000003', 'hr@xinglan.example',
  1, '资质材料齐全，审核通过', '2026-10-09 15:00:00', 1,
  '2026-10-08 10:30:00', '2026-10-09 15:00:00', 0
);

INSERT INTO stu_resume (
  id, user_id, title, is_default, education_exp, project_exp, internship_exp,
  skill_desc, self_evaluation, attachment_url, create_time, update_time, deleted
) VALUES (
  1, 2, '陈晓-校招简历', 1,
  '滨海理工大学，计算机科学与技术，本科，2026 届。',
  '校园就业信息小站：用 Spring Boot 与 Vue 完成职位检索和简历投递，MySQL 存储业务数据。',
  '无正式实习，课程项目中负责接口与表结构设计。',
  'Java、Spring Boot、MySQL、Python、Spark 入门、Vue。',
  '希望从事后端或数据开发，能接受北京或深圳。',
  NULL, '2026-10-18 14:00:00', '2026-10-18 14:00:00', 0
);

INSERT INTO job_position (
  id, company_id, category_id, title, tech_direction, province, city, district, address,
  salary_min, salary_max, salary_months, education, experience_req, job_type, headcount,
  description, requirement, welfare,
  shelf_status, audit_status, audit_remark, audit_time, auditor_id, publish_time,
  view_count, favorite_count, apply_count, create_time, update_time, deleted
) VALUES
(
  1, 1, 2, 'Java后端开发工程师（校招）', '后端开发', '北京', '北京', '海淀区',
  '北京市海淀区中关村示例大厦',
  15000, 25000, 13, 2, 1, 3, 8,
  '参与业务系统接口开发与表结构设计，配合前端完成校招相关功能。',
  '熟悉 Java、Spring Boot 和 MySQL，了解 Redis，具备良好的沟通能力。',
  '五险一金、带薪年假、餐补',
  1, 1, '职位信息完整，审核通过', '2026-10-15 11:00:00', 1, '2026-10-15 11:30:00',
  1, 0, 1, '2026-10-14 16:00:00', '2026-10-21 10:00:00', 0
),
(
  2, 1, 4, '大数据开发工程师（校招）', '数据开发', '广东', '深圳', '南山区',
  '深圳市南山区科技园示例路88号',
  18000, 30000, 14, 2, 1, 3, 5,
  '参与离线数仓与指标计算，使用 Spark 处理招聘与行为数据。',
  '熟悉 Python 或 Java，了解 Spark、Hadoop，有 SQL 基础。',
  '五险一金、补充公积金、租房补贴',
  1, 1, '职位信息完整，审核通过', '2026-10-15 11:10:00', 1, '2026-10-15 11:40:00',
  1, 1, 0, '2026-10-14 16:20:00', '2026-10-21 09:55:00', 0
);

INSERT INTO job_position_tag (
  id, position_id, tag_id, create_time, update_time, deleted
) VALUES
  (1, 1, 1, '2026-10-14 16:05:00', '2026-10-14 16:05:00', 0),
  (2, 1, 2, '2026-10-14 16:05:00', '2026-10-14 16:05:00', 0),
  (3, 1, 3, '2026-10-14 16:05:00', '2026-10-14 16:05:00', 0),
  (4, 1, 4, '2026-10-14 16:05:00', '2026-10-14 16:05:00', 0),
  (5, 2, 6, '2026-10-14 16:25:00', '2026-10-14 16:25:00', 0),
  (6, 2, 7, '2026-10-14 16:25:00', '2026-10-14 16:25:00', 0),
  (7, 2, 8, '2026-10-14 16:25:00', '2026-10-14 16:25:00', 0),
  (8, 2, 9, '2026-10-14 16:25:00', '2026-10-14 16:25:00', 0);

INSERT INTO job_favorite (
  id, user_id, position_id, create_time, update_time, deleted
) VALUES (
  1, 2, 2, '2026-10-21 09:55:00', '2026-10-21 09:55:00', 0
);

INSERT INTO job_application (
  id, user_id, position_id, company_id, resume_id, status, remark, apply_time,
  create_time, update_time, deleted
) VALUES (
  1, 2, 1, 1, 1, 2, '笔试通过，已安排技术一面', '2026-10-21 10:00:00',
  '2026-10-21 10:00:00', '2026-10-24 15:00:00', 0
);

INSERT INTO job_application_log (
  id, application_id, from_status, to_status, operator_id, remark,
  create_time, update_time, deleted
) VALUES
  (1, 1, NULL, 0, 2, '学生提交投递', '2026-10-21 10:00:00', '2026-10-21 10:00:00', 0),
  (2, 1, 0, 1, 3, '初筛通过，进入笔试', '2026-10-22 11:00:00', '2026-10-22 11:00:00', 0),
  (3, 1, 1, 2, 3, '笔试通过，进入面试', '2026-10-24 15:00:00', '2026-10-24 15:00:00', 0);

INSERT INTO job_interview (
  id, application_id, user_id, company_id, position_id, round_no, round_name,
  interview_time, interview_type, location, meeting_url, contact_name, contact_phone,
  interview_status, remind_ahead_minutes, remind_status, remind_time, remark,
  create_time, update_time, deleted
) VALUES (
  1, 1, 2, 1, 1, 1, '技术一面',
  '2026-11-06 14:00:00', 1, NULL, 'https://meet.example.com/xinglan-demo', '周宁', '13800000003',
  0, 1440, 0, NULL, '请提前十分钟进入会议',
  '2026-10-24 15:10:00', '2026-10-24 15:10:00', 0
);

INSERT INTO com_post (
  id, user_id, company_id, position_id, post_type, title, content, rating,
  audit_status, audit_remark, audit_time, auditor_id, like_count,
  create_time, update_time, deleted
) VALUES (
  1, 2, 1, 1, 1, '星澜科技 Java 后端一面准备记录',
  '笔试侧重 Java 基础、SQL 和项目经历。面试通知会给线上会议链接，建议提前调试设备。本文为演示面经。',
  NULL, 1, '内容属实，审核通过', '2026-10-25 09:30:00', 1, 3,
  '2026-10-25 09:00:00', '2026-10-25 09:30:00', 0
);

INSERT INTO com_comment (
  id, post_id, user_id, content, audit_status, audit_remark, audit_time, auditor_id,
  create_time, update_time, deleted
) VALUES (
  1, 1, 3, '感谢分享，补录通知会在站内公告发布。',
  0, NULL, NULL, NULL,
  '2026-10-25 16:20:00', '2026-10-25 16:20:00', 0
);

INSERT INTO cms_article (
  id, article_type, title, cover_url, summary, content, publisher_id, publish_time,
  top_flag, status, view_count, create_time, update_time, deleted
) VALUES
(
  1, 1, '2026 年秋季校园双选会公告', '/upload/cover/fair.png',
  '滨海理工大学秋季双选会将于 11 月在体育馆举行，请企业提前完成资质审核。',
  '时间：2026-11-12 09:00 至 16:00。地点：滨海理工大学体育馆。参会企业须完成账号与资质审核，职位保持上架。学生凭学号入场并可通过平台提前投递。',
  1, '2026-10-12 10:00:00', 1, 1, 12,
  '2026-10-12 09:40:00', '2026-10-12 10:00:00', 0
),
(
  2, 2, '高校毕业生就业服务要点', '/upload/cover/policy.png',
  '演示用就业政策摘要，正式环境可由 RAG 服务切片后写入向量库。',
  '高校应届毕业生求职应关注各地公共就业服务、校园双选会安排以及劳动合同签订、社会保险缴纳等基本权益。本段为平台演示知识，非正式法规原文。',
  1, '2026-10-16 10:00:00', 0, 1, 8,
  '2026-10-16 09:30:00', '2026-10-16 10:00:00', 0
);

INSERT INTO cms_banner (
  id, title, image_url, link_url, sort_no, status, start_time, end_time,
  create_time, update_time, deleted
) VALUES (
  1, '秋季校园双选会', '/upload/banner/career-fair.png', '/article/1',
  1, 1, '2026-10-12 00:00:00', '2026-12-31 23:59:59',
  '2026-10-12 10:05:00', '2026-10-12 10:05:00', 0
);

INSERT INTO user_behavior_log (
  id, user_id, behavior_type, target_type, target_id, weight,
  create_time, update_time, deleted
) VALUES
  (1, 2, 1, 1, 1, 1, '2026-10-21 09:40:00', '2026-10-21 09:40:00', 0),
  (2, 2, 1, 1, 2, 1, '2026-10-21 09:50:00', '2026-10-21 09:50:00', 0),
  (3, 2, 2, 1, 2, 3, '2026-10-21 09:55:00', '2026-10-21 09:55:00', 0),
  (4, 2, 3, 1, 1, 5, '2026-10-21 10:00:00', '2026-10-21 10:00:00', 0);

INSERT INTO spark_task_log (
  id, batch_no, task_code, task_name, status, start_time, end_time,
  input_count, output_count, result_msg, error_msg, params_json,
  create_time, update_time, deleted
) VALUES
(
  1, '2026103001', 'clean', '行为与职位清洗', 1,
  '2026-10-30 02:00:00', '2026-10-30 02:03:00', 4, 4,
  '演示批次，过滤逻辑删除记录', NULL,
  '{"source":"job_platform","tables":["job_position","user_behavior_log"]}',
  '2026-10-30 02:03:00', '2026-10-30 02:03:00', 0
),
(
  2, '2026103001', 'aggregate', '薪资与趋势聚合', 1,
  '2026-10-30 02:03:10', '2026-10-30 02:06:00', 4, 10,
  '演示批次，写出城市薪资 2 行、技术趋势 6 行、地区分布 2 行', NULL,
  '{"grain":["city","tech_direction","month","province"]}',
  '2026-10-30 02:06:00', '2026-10-30 02:06:00', 0
),
(
  3, '2026103001', 'salary_regression', '薪资线性回归', 1,
  '2026-10-30 02:06:10', '2026-10-30 02:08:00', 4, 2,
  '演示模型 lr_v1，正式环境由 PySpark 训练后回写', NULL,
  '{"model":"lr_v1","features":["city","techDirection","education","experienceYears"]}',
  '2026-10-30 02:08:00', '2026-10-30 02:08:00', 0
),
(
  4, '2026103001', 'user_cf', 'User-CF 推荐', 1,
  '2026-10-30 02:08:10', '2026-10-30 02:09:20', 4, 1,
  '隐式反馈权重：浏览1、收藏3、投递5', NULL,
  '{"neighbors":20,"weights":{"view":1,"favorite":3,"apply":5}}',
  '2026-10-30 02:09:20', '2026-10-30 02:09:20', 0
),
(
  5, '2026103001', 'content_match', '内容匹配', 1,
  '2026-10-30 02:09:30', '2026-10-30 02:10:20', 2, 3,
  '写出内容匹配 2 行，并与协同过滤合成融合分 1 行', NULL,
  '{"fields":["stu_skill","job_position_tag","expect_direction"]}',
  '2026-10-30 02:10:20', '2026-10-30 02:10:20', 0
);

INSERT INTO spark_salary_stat (
  id, batch_no, province, city, tech_direction, job_count,
  avg_salary, median_salary, min_salary, max_salary, p25_salary, p75_salary,
  is_latest, create_time, update_time, deleted
) VALUES
  (1, '2026103001', '北京', '北京', '后端开发', 1, 20000.00, 20000.00, 15000.00, 25000.00, 17000.00, 23000.00, 1, '2026-10-30 02:06:00', '2026-10-30 02:06:00', 0),
  (2, '2026103001', '广东', '深圳', '数据开发', 1, 24000.00, 24000.00, 18000.00, 30000.00, 20000.00, 28000.00, 1, '2026-10-30 02:06:00', '2026-10-30 02:06:00', 0);

INSERT INTO spark_tech_trend (
  id, batch_no, stat_month, tag_name, tech_direction, demand_count, avg_salary, mom_rate,
  is_latest, create_time, update_time, deleted
) VALUES
  (1, '2026103001', '2026-08', 'Java',  '后端开发', 1, 19000.00, NULL,   1, '2026-10-30 02:06:00', '2026-10-30 02:06:00', 0),
  (2, '2026103001', '2026-09', 'Java',  '后端开发', 1, 19500.00, 0.0000, 1, '2026-10-30 02:06:00', '2026-10-30 02:06:00', 0),
  (3, '2026103001', '2026-10', 'Java',  '后端开发', 1, 20000.00, 0.0000, 1, '2026-10-30 02:06:00', '2026-10-30 02:06:00', 0),
  (4, '2026103001', '2026-08', 'Spark', '数据开发', 1, 22000.00, NULL,   1, '2026-10-30 02:06:00', '2026-10-30 02:06:00', 0),
  (5, '2026103001', '2026-09', 'Spark', '数据开发', 1, 23000.00, 0.0000, 1, '2026-10-30 02:06:00', '2026-10-30 02:06:00', 0),
  (6, '2026103001', '2026-10', 'Spark', '数据开发', 1, 24000.00, 0.0000, 1, '2026-10-30 02:06:00', '2026-10-30 02:06:00', 0);

INSERT INTO spark_region_dist (
  id, batch_no, province_name, adcode, job_count, company_count, avg_salary, apply_count,
  is_latest, create_time, update_time, deleted
) VALUES
  (1, '2026103001', '北京', '110000', 1, 1, 20000.00, 1, 1, '2026-10-30 02:06:00', '2026-10-30 02:06:00', 0),
  (2, '2026103001', '广东', '440000', 1, 1, 24000.00, 0, 1, '2026-10-30 02:06:00', '2026-10-30 02:06:00', 0);

INSERT INTO spark_salary_predict (
  id, batch_no, user_id, position_id, province, city, tech_direction, education,
  experience_years, predicted_salary, ci_low, ci_high, model_version, feature_json,
  is_latest, create_time, update_time, deleted
) VALUES
(
  1, '2026103001', 2, 1, '北京', '北京', '后端开发', 2,
  0.0, 18500.00, 15000.00, 23000.00, 'lr_v1',
  '{"city":"北京","techDirection":"后端开发","education":2,"experienceYears":0}',
  1, '2026-10-30 02:08:00', '2026-10-30 02:08:00', 0
),
(
  2, '2026103001', 2, 2, '广东', '深圳', '数据开发', 2,
  0.0, 22000.00, 18000.00, 27000.00, 'lr_v1',
  '{"city":"深圳","techDirection":"数据开发","education":2,"experienceYears":0}',
  1, '2026-10-30 02:08:00', '2026-10-30 02:08:00', 0
);

INSERT INTO spark_recommend (
  id, batch_no, user_id, position_id, algo, match_score, cf_score, content_score,
  rank_no, reason, is_latest, create_time, update_time, deleted
) VALUES
(
  1, '2026103001', 2, 1, 2, 88.00, NULL, 88.00,
  1, '技能重合 Java、Spring Boot、MySQL，期望方向为后端开发',
  1, '2026-10-30 02:10:20', '2026-10-30 02:10:20', 0
),
(
  2, '2026103001', 2, 1, 3, 82.00, 55.00, 88.00,
  2, '融合分以内容匹配为主，协同过滤作为校正',
  1, '2026-10-30 02:10:20', '2026-10-30 02:10:20', 0
),
(
  3, '2026103001', 2, 2, 1, 70.00, 70.00, NULL,
  3, '学生对深圳数据岗位有浏览和收藏行为',
  1, '2026-10-30 02:09:20', '2026-10-30 02:09:20', 0
),
(
  4, '2026103001', 2, 2, 2, 64.00, NULL, 64.00,
  4, '技能重合 Python、Spark，与数据开发岗位部分匹配',
  1, '2026-10-30 02:10:20', '2026-10-30 02:10:20', 0
);

INSERT INTO rag_document (
  id, doc_type, title, source_type, source_id, chunk_no, content, content_hash,
  chroma_collection, chroma_id, embed_status, create_time, update_time, deleted
) VALUES (
  1, 1, '高校毕业生就业服务要点', 3, 2, 0,
  '高校应届毕业生求职应关注各地公共就业服务、校园双选会安排以及劳动合同签订、社会保险缴纳等基本权益。本段为平台演示知识，非正式法规原文。',
  'd139b2fe2b9c0d1393161a56e83c202cac1041f419a61aea85710a7876fa767f',
  NULL, NULL, 0,
  '2026-10-16 10:20:00', '2026-10-16 10:20:00', 0
);

INSERT INTO ai_session (
  id, user_id, agent_type, title, create_time, update_time, deleted
) VALUES (
  1, 2, 1, '校招岗位匹配咨询', '2026-10-29 21:00:00', '2026-10-29 21:01:00', 0
);

INSERT INTO ai_message (
  id, session_id, msg_role, content, token_count, create_time, update_time, deleted
) VALUES
(
  1, 1, 'user',
  '我的技能更适合星澜科技的哪个校招岗位？',
  24, '2026-10-29 21:00:00', '2026-10-29 21:00:00', 0
),
(
  2, 1, 'assistant',
  'Java 后端开发工程师与你的 Java、Spring Boot、MySQL 重合更高；大数据开发工程师覆盖了你的 Python 和 Spark。建议优先投递后端岗位，并把数据岗位作为备选。',
  68, '2026-10-29 21:01:00', '2026-10-29 21:01:00', 0
);

COMMIT;
