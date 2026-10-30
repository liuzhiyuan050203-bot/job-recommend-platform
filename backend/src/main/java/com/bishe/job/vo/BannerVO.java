package com.bishe.job.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class BannerVO {

    private Long id;
    private String title;
    private String imageUrl;
    private String linkUrl;
    private Integer sortNo;
    private Integer status;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
    private LocalDateTime createTime;
}
