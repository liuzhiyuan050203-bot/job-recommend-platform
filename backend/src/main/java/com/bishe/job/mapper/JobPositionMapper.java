package com.bishe.job.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bishe.job.entity.JobPosition;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface JobPositionMapper extends BaseMapper<JobPosition> {

    @Update("UPDATE job_position SET view_count = IFNULL(view_count, 0) + 1 WHERE id = #{id} AND deleted = 0")
    int incrView(@Param("id") Long id);

    @Update("UPDATE job_position SET favorite_count = IFNULL(favorite_count, 0) + 1 WHERE id = #{id} AND deleted = 0")
    int incrFavorite(@Param("id") Long id);

    @Update("UPDATE job_position SET favorite_count = GREATEST(IFNULL(favorite_count, 0) - 1, 0) WHERE id = #{id} AND deleted = 0")
    int decrFavorite(@Param("id") Long id);

    @Update("UPDATE job_position SET apply_count = IFNULL(apply_count, 0) + 1 WHERE id = #{id} AND deleted = 0")
    int incrApply(@Param("id") Long id);
}
