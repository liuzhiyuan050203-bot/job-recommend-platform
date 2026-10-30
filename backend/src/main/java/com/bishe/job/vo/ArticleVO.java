package com.bishe.job.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class ArticleVO {

    private Long id;
    private Integer articleType;
    private String articleTypeName;
    private String title;
    private String coverUrl;
    private String summary;
    private String content;
    private Long publisherId;
    private String publisherName;
    private LocalDateTime publishTime;
    private Integer topFlag;
    private Integer status;
    private Integer viewCount;
    private LocalDateTime createTime;
}
