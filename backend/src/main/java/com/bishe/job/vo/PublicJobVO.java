package com.bishe.job.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 公开职位卡片与详情。列表不填 description / requirement。
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
}
