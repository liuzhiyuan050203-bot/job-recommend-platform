package com.bishe.job.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bishe.job.entity.StuSkill;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface StuSkillMapper extends BaseMapper<StuSkill> {

    @Select("SELECT * FROM stu_skill WHERE user_id = #{userId} AND tag_id = #{tagId} LIMIT 1")
    StuSkill selectWithDeleted(@Param("userId") Long userId, @Param("tagId") Long tagId);

    @Update("UPDATE stu_skill SET proficiency = #{proficiency}, deleted = 0, update_time = NOW() WHERE id = #{id}")
    int restoreSkill(@Param("id") Long id, @Param("proficiency") Integer proficiency);
}
