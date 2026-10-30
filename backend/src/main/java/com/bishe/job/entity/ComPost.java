package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 面经与企业评价，对应 com_post
 */
@Data
@TableName("com_post")
public class ComPost {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    private Long companyId;

    private Long positionId;

    /** 帖子类型：1面经 2企业评价 */
    private Integer postType;

    private String title;

    private String content;

    /** 评分 1到5 */
    private Integer rating;

    /** 审核状态：0待审核 1已通过 2已驳回 */
    private Integer auditStatus;

    private String auditRemark;

    private LocalDateTime auditTime;

    private Long auditorId;

    private Integer likeCount;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
