package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 简历投递，对应 job_application。
 * 状态：0待初筛 1笔试 2面试中 3已录用 4未通过。
 */
@Data
@TableName("job_application")
public class JobApplication {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;

    private Long positionId;

    private Long companyId;

    private Long resumeId;

    private Integer status;

    private String remark;

    private LocalDateTime applyTime;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
