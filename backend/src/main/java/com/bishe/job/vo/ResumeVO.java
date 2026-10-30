package com.bishe.job.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class ResumeVO {

    private Long id;
    private Long userId;
    private String title;
    private Integer isDefault;
    private String educationExp;
    private String projectExp;
    private String internshipExp;
    private String skillDesc;
    private String selfEvaluation;
    private String attachmentUrl;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;
}
