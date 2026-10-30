package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 用户行为日志，对应 user_behavior_log。
 * behavior_type：1浏览 2收藏 3投递；target_type：1职位。
 */
@Data
@TableName("user_behavior_log")
public class UserBehaviorLog {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    private Integer behaviorType;

    private Integer targetType;

    private Long targetId;

    private Integer weight;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
