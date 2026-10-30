package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 投递状态变更日志，对应 job_application_log。新建投递时 from_status 为空。
 */
@Data
@TableName("job_application_log")
public class JobApplicationLog {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long applicationId;

    private Integer fromStatus;

    private Integer toStatus;

    private Long operatorId;

    private String remark;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
