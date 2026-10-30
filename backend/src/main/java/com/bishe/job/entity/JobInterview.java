package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 笔试/面试日程，对应 job_interview。
 * interview_type：1线上 2线下；interview_status：0待进行 1已完成 2已取消 3学生缺席。
 */
@Data
@TableName("job_interview")
public class JobInterview {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long applicationId;

    private Long userId;

    private Long companyId;

    private Long positionId;

    private Integer roundNo;

    private String roundName;

    private LocalDateTime interviewTime;

    /** 1线上 2线下 */
    private Integer interviewType;

    private String location;

    private String meetingUrl;

    private String contactName;

    private String contactPhone;

    /** 0待进行 1已完成 2已取消 3学生缺席 */
    private Integer interviewStatus;

    private Integer remindAheadMinutes;

    private Integer remindStatus;

    private LocalDateTime remindTime;

    private String remark;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;

    @TableLogic
    private Integer deleted;
}
