package com.bishe.job.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class PostVO {

    private Long id;
    private Long userId;
    private String authorName;
    private String authorAvatar;
    private Long companyId;
    private String companyName;
    private Long positionId;
    private String positionTitle;
    private Integer postType;
    private String postTypeName;
    private String title;
    private String content;
    private Integer rating;
    private Integer auditStatus;
    private String auditRemark;
    private LocalDateTime auditTime;
    private Integer likeCount;
    private Integer commentCount;
    private LocalDateTime createTime;
}
