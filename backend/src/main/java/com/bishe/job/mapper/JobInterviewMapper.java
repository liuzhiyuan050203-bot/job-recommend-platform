package com.bishe.job.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bishe.job.entity.JobInterview;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface JobInterviewMapper extends BaseMapper<JobInterview> {

    @Select("SELECT MAX(round_no) FROM job_interview WHERE application_id = #{applicationId} AND deleted = 0")
    Integer selectMaxRound(@Param("applicationId") Long applicationId);
}
