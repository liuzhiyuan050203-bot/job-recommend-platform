package com.bishe.job.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bishe.job.entity.JobPositionTag;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.List;

@Mapper
public interface JobPositionTagMapper extends BaseMapper<JobPositionTag> {

    /** 含已逻辑删除的关联，便于按唯一键恢复 */
    @Select("SELECT * FROM job_position_tag WHERE position_id = #{positionId}")
    List<JobPositionTag> selectAllByPosition(@Param("positionId") Long positionId);

    @Update("UPDATE job_position_tag SET deleted = 0, update_time = NOW() WHERE id = #{id}")
    int restore(@Param("id") Long id);
}
