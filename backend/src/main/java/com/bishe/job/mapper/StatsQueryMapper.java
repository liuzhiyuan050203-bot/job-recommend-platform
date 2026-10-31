package com.bishe.job.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

import java.math.BigDecimal;

/**
 * 概览里不依赖 Spark 结果表的实时计数。
 */
@Mapper
public interface StatsQueryMapper {

    @Select("SELECT COUNT(*) FROM job_position WHERE deleted = 0 AND audit_status = 1")
    long countApprovedJobs();

    @Select("SELECT COUNT(*) FROM ent_company WHERE deleted = 0 AND audit_status = 1")
    long countApprovedCompanies();

    @Select("SELECT COUNT(*) FROM sys_user WHERE deleted = 0 AND role = 1 AND status = 1")
    long countActiveStudents();

    @Select("SELECT COUNT(DISTINCT city) FROM job_position WHERE deleted = 0 AND audit_status = 1 AND city IS NOT NULL AND city <> ''")
    long countJobCities();

    @Select("SELECT AVG((salary_min + salary_max) / 2) FROM job_position WHERE deleted = 0 AND audit_status = 1")
    BigDecimal avgApprovedSalary();
}
