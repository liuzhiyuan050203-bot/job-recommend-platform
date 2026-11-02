package com.bishe.job.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 公开职位卡片与详情。列表不填 description / requirement。
 * 详情的 description / requirement / welfare 是整理后的纯文本，原始抓取元数据见 dataSource。
 */
@Data
public class PublicJobVO {

    private Long id;
    private String title;
    private String techDirection;
    private Long categoryId;
    private String province;
    private String city;
    private String district;
    private String address;
    private Integer salaryMin;
    private Integer salaryMax;
    private Integer salaryMonths;
    private Integer education;
    private Integer experienceReq;
    private Integer jobType;
    private Integer headcount;
    private String welfare;
    private String description;
    private String requirement;
    private Long companyId;
    private String companyName;
    private String companyLogo;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime publishTime;

    private Integer viewCount;
    private Integer favoriteCount;
    private Integer applyCount;
    private Integer shelfStatus;
    private Integer auditStatus;
    private List<Long> tagIds = new ArrayList<>();
    private List<String> tagNames = new ArrayList<>();
    /** 当前学生是否已收藏；匿名为 false */
    private Boolean favorited = false;
    /** 当前学生是否已投递；匿名为 false */
    private Boolean applied = false;

    /** 详情页：整理后的岗位职责条目（去掉抓取元数据与序号） */
    private List<String> descriptionItems = new ArrayList<>();
    /** 详情页：整理后的任职要求条目（爬虫 JSON 已拆开） */
    private List<String> requirementItems = new ArrayList<>();
    /** 详情页：数据来源（企业发布 / 校招官网同步） */
    private JobSourceVO dataSource;
    /** 薪资是否为平台估算（真实职位官网未公布薪资） */
    private Boolean salaryEstimated = false;
    private String salaryNote;
}
