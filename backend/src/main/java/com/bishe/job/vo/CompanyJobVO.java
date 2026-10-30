package com.bishe.job.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Data
public class CompanyJobVO {

    private Long id;
    private Long companyId;
    private Long categoryId;
    private String categoryName;
    private String title;
    private String techDirection;
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
    private String description;
    private String requirement;
    private String welfare;
    private Integer shelfStatus;
    private Integer auditStatus;
    private String auditRemark;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime auditTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime publishTime;

    private Integer viewCount;
    private Integer favoriteCount;
    private Integer applyCount;
    private List<Long> tagIds = new ArrayList<>();
    private List<String> tagNames = new ArrayList<>();

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;
}
