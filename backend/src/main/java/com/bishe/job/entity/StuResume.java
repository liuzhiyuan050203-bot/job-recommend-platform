package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 学生在线简历，对应 stu_resume。一个学生可有多份。
 */
@Data
@TableName("stu_resume")
public class StuResume {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    private String title;

    /** 是否默认简历：0否 1是 */
    private Integer isDefault;

    private String educationExp;

    private String projectExp;

    private String internshipExp;

    private String skillDesc;

    private String selfEvaluation;

    private String attachmentUrl;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
