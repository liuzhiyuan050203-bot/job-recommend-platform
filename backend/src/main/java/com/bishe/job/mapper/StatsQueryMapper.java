package com.bishe.job.mapper;

import com.bishe.job.vo.DashboardAggVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 概览和仪表盘里不依赖 Spark 结果表的实时聚合。
 */
@Mapper
public interface StatsQueryMapper {

    @Select("SELECT COUNT(*) FROM job_position WHERE deleted = 0 AND audit_status = 1")
    long countApprovedJobs();

    @Select("SELECT COUNT(*) FROM ent_company WHERE deleted = 0 AND audit_status = 1")
    long countApprovedCompanies();

    @Select("SELECT COUNT(*) FROM sys_user WHERE deleted = 0 AND role = 1 AND status = 1")
    long countActiveStudents();

    @Select("SELECT COUNT(*) FROM job_application WHERE deleted = 0")
    long countApplications();

    @Select("SELECT COUNT(DISTINCT city) FROM job_position WHERE deleted = 0 AND audit_status = 1 AND city IS NOT NULL AND city <> ''")
    long countJobCities();

    @Select("SELECT AVG((salary_min + salary_max) / 2) FROM job_position WHERE deleted = 0 AND audit_status = 1")
    BigDecimal avgApprovedSalary();

    @Select("""
            SELECT DATE_FORMAT(COALESCE(publish_time, create_time), '%Y-%m') AS label,
                   COUNT(*) AS total
            FROM job_position
            WHERE deleted = 0
              AND audit_status = 1
              AND COALESCE(publish_time, create_time) >= #{start}
              AND COALESCE(publish_time, create_time) < #{end}
            GROUP BY DATE_FORMAT(COALESCE(publish_time, create_time), '%Y-%m')
            """)
    List<DashboardAggVO> monthlyApprovedJobs(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);

    @Select("""
            SELECT DATE_FORMAT(create_time, '%Y-%m') AS label,
                   COUNT(*) AS total
            FROM job_application
            WHERE deleted = 0
              AND create_time >= #{start}
              AND create_time < #{end}
            GROUP BY DATE_FORMAT(create_time, '%Y-%m')
            """)
    List<DashboardAggVO> monthlyApplications(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);

    @Select("""
            SELECT st.name AS label, ROUND(AVG(ss.proficiency), 2) AS avgLevel
            FROM stu_skill ss
            INNER JOIN skill_tag st ON st.id = ss.tag_id AND st.deleted = 0
            WHERE ss.deleted = 0
            GROUP BY st.id, st.name
            """)
    List<DashboardAggVO> skillAvgLevels();

    @Select("""
            SELECT st.name AS label, COUNT(*) AS total
            FROM job_position p
            INNER JOIN job_position_tag t ON t.position_id = p.id AND t.deleted = 0
            INNER JOIN skill_tag st ON st.id = t.tag_id AND st.deleted = 0
            WHERE p.deleted = 0 AND p.audit_status = 1 AND p.shelf_status = 1
            GROUP BY st.id, st.name
            ORDER BY total DESC, st.name ASC
            LIMIT 12
            """)
    List<DashboardAggVO> hotJobTags();

    @Select("""
            SELECT st.name AS label, COUNT(DISTINCT a.user_id) AS total
            FROM job_application a
            INNER JOIN stu_skill ss ON ss.user_id = a.user_id AND ss.deleted = 0
            INNER JOIN skill_tag st ON st.id = ss.tag_id AND st.deleted = 0
            WHERE a.company_id = #{companyId} AND a.deleted = 0
            GROUP BY st.id, st.name
            ORDER BY total DESC, st.name ASC
            LIMIT 15
            """)
    List<DashboardAggVO> applicantSkillCounts(@Param("companyId") Long companyId);

    @Select("SELECT COUNT(*) FROM ai_session WHERE deleted = 0")
    long countAiSessions();

    @Select("SELECT COUNT(*) FROM ai_message WHERE deleted = 0")
    long countAiMessages();
}
