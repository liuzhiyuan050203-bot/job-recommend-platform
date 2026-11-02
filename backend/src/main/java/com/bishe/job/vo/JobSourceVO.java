package com.bishe.job.vo;

import lombok.Data;

/**
 * 职位数据来源。企业在平台发布的职位 type=PLATFORM；从校招官网公开接口同步的职位 type=CRAWLER，
 * 附带官网名称、站点、投递链接与抓取时间，前端渲染为来源徽标。
 */
@Data
public class JobSourceVO {
    public static final String PLATFORM = "PLATFORM";
    public static final String CRAWLER = "CRAWLER";

    private String type;
    /** 徽标文字，如「字节跳动校招官网」「企业发布」 */
    private String label;
    private String site;
    private String applyUrl;
    private String crawledAt;
    private String project;
    private String workCities;
}
