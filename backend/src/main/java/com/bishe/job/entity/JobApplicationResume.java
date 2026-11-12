package com.bishe.job.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 投递时的简历快照，对应 job_application_resume。企业查看以此为准。
 */
@Data
@TableName("job_application_resume")
public class JobApplicationResume {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long applicationId;

    private Long resumeId;

    private String title;

    private String educationExp;

    private String projectExp;

    private String internshipExp;

    private String skillDesc;

    private String selfEvaluation;

    private String attachmentUrl;

    private String contentHash;

    private LocalDateTime capturedAt;
}
