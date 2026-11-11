package com.bishe.job.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bishe.job.entity.StuResume;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface StuResumeMapper extends BaseMapper<StuResume> {

    /**
     * 按主键读取简历，包含学生已删除（逻辑删除）的记录。
     * 仅用于投递记录：投递时简历已发给企业，学生事后删除简历不应让投递详情变空或报错。
     */
    @Select("SELECT * FROM stu_resume WHERE id = #{id}")
    StuResume selectByIdIncludingDeleted(@Param("id") Long id);
}
