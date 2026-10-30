package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 公告、新闻与就业政策，对应 cms_article
 */
@Data
@TableName("cms_article")
public class CmsArticle {

    @TableId(type = IdType.AUTO)
    private Long id;

    /** 内容类型：1双选会公告 2就业政策 3新闻资讯 */
    private Integer articleType;

    private String title;

    private String coverUrl;

    private String summary;

    private String content;

    private Long publisherId;

    private LocalDateTime publishTime;

    /** 是否置顶：0否 1是 */
    private Integer topFlag;

    /** 发布状态：0草稿 1已发布 2已下线 */
    private Integer status;

    private Integer viewCount;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
