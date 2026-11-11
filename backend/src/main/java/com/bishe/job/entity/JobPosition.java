package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 招聘职位，对应 job_position
 */
@Data
@TableName("job_position")
public class JobPosition {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long companyId;

    private Long categoryId;

    private String title;

    private String techDirection;

    private String province;

    private String city;

    private String district;

    private String address;

    private Integer salaryMin;

    private Integer salaryMax;

    private Integer salaryMonths;

    /** 学历要求：0不限 1专科 2本科 3硕士 4博士 */
    private Integer education;

    /** 经验要求：0不限 1应届生 2一年以内 3一到三年 4三到五年 5五年以上 */
    private Integer experienceReq;

    /** 工作性质：1全职 2实习 3校招 */
    private Integer jobType;

    private Integer headcount;

    private String description;

    private String requirement;

    private String welfare;

    /** 数据来源：platform 平台发布 / self_crawl 自爬校招官网 / ext_ats 外部扩充库（飞书招聘公开门户） */
    private String dataSource;

    /** 上下架状态：0下架 1上架 */
    private Integer shelfStatus;

    /** 审核状态：0待审核 1已通过 2已驳回 */
    private Integer auditStatus;

    private String auditRemark;

    private LocalDateTime auditTime;

    private Long auditorId;

    private LocalDateTime publishTime;

    private Integer viewCount;

    private Integer favoriteCount;

    private Integer applyCount;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
