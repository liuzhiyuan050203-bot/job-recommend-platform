package com.bishe.job.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 发送笔试或面试通知。noticeType：1笔试 2面试；interviewType：1线上 2线下。
 */
@Data
public class InterviewNoticeDTO {

    @NotNull(message = "通知类型不能为空")
    @Min(value = 1, message = "通知类型：1笔试 2面试")
    @Max(value = 2, message = "通知类型：1笔试 2面试")
    private Integer noticeType;

    @NotNull(message = "时间不能为空")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime interviewTime;

    @NotNull(message = "方式不能为空")
    @Min(value = 1, message = "方式：1线上 2线下")
    @Max(value = 2, message = "方式：1线上 2线下")
    private Integer interviewType;

    @Size(max = 255, message = "地点长度不能超过 255")
    private String location;

    @Size(max = 512, message = "链接长度不能超过 512")
    private String meetingUrl;

    @Size(max = 64, message = "联系人长度不能超过 64")
    private String contactName;

    @Size(max = 20, message = "联系电话长度不能超过 20")
    private String contactPhone;

    @Size(max = 64, message = "轮次名称长度不能超过 64")
    private String roundName;

    @Size(max = 500, message = "备注长度不能超过 500")
    private String remark;
}
