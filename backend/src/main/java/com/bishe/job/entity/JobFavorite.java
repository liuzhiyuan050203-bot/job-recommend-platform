package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 职位收藏，对应 job_favorite。再次收藏时把 deleted 改回 0。
 */
@Data
@TableName("job_favorite")
public class JobFavorite {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    private Long positionId;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
