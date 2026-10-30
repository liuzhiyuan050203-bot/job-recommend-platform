package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 职位与技能标签关联，对应 job_position_tag。
 */
@Data
@TableName("job_position_tag")
public class JobPositionTag {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long positionId;

    private Long tagId;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
