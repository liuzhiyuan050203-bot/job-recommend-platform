package com.bishe.job.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class AdminJobVO {

    private Long id;
    private Long companyId;
    private String companyName;
    private Long categoryId;
    private String categoryName;
    private String title;
    /** 数据来源代码：platform / self_crawl / ext_ats */
    private String sourceCode;
    private String techDirection;
    private String province;
    private String city;
    private String district;
    private Integer salaryMin;
    private Integer salaryMax;
    private Integer salaryMonths;
    private Integer education;
    private Integer experienceReq;
    private Integer jobType;
    private Integer headcount;
    private String description;
    private String requirement;
    private String welfare;
    private Integer shelfStatus;
    private Integer auditStatus;
    private String auditRemark;
    private LocalDateTime auditTime;
    private Long auditorId;
    private LocalDateTime publishTime;
    private Integer viewCount;
    private Integer favoriteCount;
    private Integer applyCount;
    private LocalDateTime createTime;
}
