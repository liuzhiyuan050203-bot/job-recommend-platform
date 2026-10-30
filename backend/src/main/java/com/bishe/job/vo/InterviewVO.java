package com.bishe.job.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class InterviewVO {

    private Long id;
    private Long applicationId;
    private Long userId;
    private String studentName;
    private Long companyId;
    private String companyName;
    private Long jobId;
    private String jobTitle;
    private Integer roundNo;
    private String roundName;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime interviewTime;

    /** 1线上 2线下 */
    private Integer interviewType;
    private String interviewTypeName;
    private String location;
    private String meetingUrl;
    private String contactName;
    private String contactPhone;
    /** 0待进行 1已完成 2已取消 3学生缺席 */
    private Integer interviewStatus;
    private String interviewStatusName;
    private String remark;
}
