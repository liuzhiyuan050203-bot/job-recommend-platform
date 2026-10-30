package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 学生档案，对应 stu_profile。一名学生一份档案。
 */
@Data
@TableName("stu_profile")
public class StuProfile {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;
    private String realName;
    /** 0 未知 1 男 2 女 */
    private Integer gender;
    private LocalDate birthday;
    private String studentNo;
    private String school;
    private String college;
    private String major;
    /** 1 专科 2 本科 3 硕士 4 博士 */
    private Integer education;
    private Integer graduationYear;
    private String expectCity;
    private Integer expectSalaryMin;
    private Integer expectSalaryMax;
    private String expectDirection;
    private String selfIntro;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
