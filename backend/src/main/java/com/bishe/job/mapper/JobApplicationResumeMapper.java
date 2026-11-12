package com.bishe.job.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bishe.job.entity.JobApplicationResume;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface JobApplicationResumeMapper extends BaseMapper<JobApplicationResume> {

    @Select("SELECT * FROM job_application_resume WHERE application_id = #{applicationId} LIMIT 1")
    JobApplicationResume selectByApplicationId(@Param("applicationId") Long applicationId);
}
