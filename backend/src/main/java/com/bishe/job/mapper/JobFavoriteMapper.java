package com.bishe.job.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bishe.job.entity.JobFavorite;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface JobFavoriteMapper extends BaseMapper<JobFavorite> {

    @Select("SELECT * FROM job_favorite WHERE user_id = #{userId} AND position_id = #{positionId} LIMIT 1")
    JobFavorite selectAny(@Param("userId") Long userId, @Param("positionId") Long positionId);

    @Update("UPDATE job_favorite SET deleted = 0, update_time = NOW() WHERE id = #{id}")
    int restore(@Param("id") Long id);
}
