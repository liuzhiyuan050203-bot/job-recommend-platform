package com.bishe.job.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class CommentVO {

    private Long id;
    private Long postId;
    private String postTitle;
    private Long userId;
    private String authorName;
    private String authorAvatar;
    private String content;
    private Integer auditStatus;
    private String auditRemark;
    private LocalDateTime auditTime;
    private LocalDateTime createTime;
}
