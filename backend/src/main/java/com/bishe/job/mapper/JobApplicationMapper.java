package com.bishe.job.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bishe.job.entity.JobApplication;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.LocalDateTime;

@Mapper
public interface JobApplicationMapper extends BaseMapper<JobApplication> {

    @Select("SELECT * FROM job_application WHERE user_id = #{userId} AND position_id = #{positionId} LIMIT 1")
    JobApplication selectAny(@Param("userId") Long userId, @Param("positionId") Long positionId);

    @Update("""
            UPDATE job_application
            SET deleted = 0, status = 0, resume_id = #{resumeId}, company_id = #{companyId},
                remark = NULL, apply_time = #{applyTime}, update_time = NOW()
            WHERE id = #{id}
            """)
    int revive(@Param("id") Long id, @Param("resumeId") Long resumeId, @Param("companyId") Long companyId,
               @Param("applyTime") LocalDateTime applyTime);
}
