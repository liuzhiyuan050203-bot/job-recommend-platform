package com.bishe.job.vo;

import com.fasterxml.jackson.annotation.JsonIgnore;
import lombok.Data;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * 学生端推荐卡片。source：batch 离线批次，realtime 实时计算，fallback 数据库兜底。
 */
@Data
public class RecommendJobVO {

    private Long positionId;
    private String title;
    /** 数据来源代码：platform / self_crawl / ext_ats，前端据此显示来源徽标与估算薪资提示 */
    private String sourceCode;
    private String companyName;
    private String city;
    private String province;
    private String techDirection;
    private Integer salaryMin;
    private Integer salaryMax;
    private Integer salaryMonths;
    private Integer education;
    private List<String> tagNames = new ArrayList<>();
    private BigDecimal matchScore;
    private BigDecimal cfScore;
    private BigDecimal contentScore;
    private Integer rankNo;
    private String reason;
    private String source;

    /** 兜底 SQL 的原始分，不返回给前端 */
    @JsonIgnore
    private Double rawScore;
    @JsonIgnore
    private Integer directionHit;
    @JsonIgnore
    private Integer cityHit;
    @JsonIgnore
    private String skillNames;
    @JsonIgnore
    private String expectCity;
    @JsonIgnore
    private String expectDirection;
    @JsonIgnore
    private Integer applyCount;
}
