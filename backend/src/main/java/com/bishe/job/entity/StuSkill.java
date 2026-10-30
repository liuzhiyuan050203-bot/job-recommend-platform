package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 学生掌握技能及熟练度，对应 stu_skill
 */
@Data
@TableName("stu_skill")
public class StuSkill {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    private Long tagId;

    /** 熟练度 1 到 5 */
    private Integer proficiency;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
