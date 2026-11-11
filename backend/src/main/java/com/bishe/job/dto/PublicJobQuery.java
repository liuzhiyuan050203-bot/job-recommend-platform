package com.bishe.job.dto;

import lombok.Data;

import java.util.List;

/**
 * 公开职位检索条件。sort 只允许 newest / salary / hot，由服务层白名单归一。
 */
@Data
public class PublicJobQuery {

    private String keyword;
    private String techDirection;
    private Long categoryId;
    private String city;
    private Integer salaryMin;
    private Integer salaryMax;
    /**
     * 学历筛选：职位要求 &lt;= 该值。0 不限，1 专科，2 本科，3 硕士，4 博士。
     */
    private Integer education;
    private Integer jobType;
    private List<Long> tagIds;
    private String sort;
    /** 数据来源：platform / self_crawl / ext_ats / internal（排除外部扩充库）；其他值忽略 */
    private String source;
}
