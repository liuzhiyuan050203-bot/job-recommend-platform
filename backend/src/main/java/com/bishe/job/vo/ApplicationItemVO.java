package com.bishe.job.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Data
public class ApplicationItemVO {

    private Long id;
    private Long userId;
    private String studentName;
    private String school;
    private String major;
    private Integer education;
    private String educationName;
    private Long jobId;
    private String jobTitle;
    private String city;
    private Long companyId;
    private String companyName;
    private Long resumeId;
    private Integer status;
    private String statusName;
    private String remark;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime applyTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;

    private List<StatusOptionVO> nextStatuses = new ArrayList<>();

    /** 企业端：候选人技能（命中职位技能的排前面） */
    private List<CandidateSkillVO> candidateSkills = new ArrayList<>();
    /** 企业端：职位要求但候选人没有的技能 */
    private List<String> missingSkills = new ArrayList<>();
    private Integer matchedSkillCount;
    private Integer jobSkillCount;
    /** 企业端：技能匹配分 0~100；职位没有技能标签时为 null */
    private Integer matchScore;
}
