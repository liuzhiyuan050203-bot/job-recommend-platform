package com.bishe.job.vo;

import lombok.Data;
import lombok.EqualsAndHashCode;

import java.util.ArrayList;
import java.util.List;

@Data
@EqualsAndHashCode(callSuper = true)
public class ApplicationDetailVO extends ApplicationItemVO {

    private String phone;
    private Integer graduationYear;
    private String expectCity;
    private ResumeVO resume;
    /** 学生投递后已删除该简历；resume 中为投递时快照（或删除前保留的内容） */
    private Boolean resumeDeleted = false;
    /** 学生在投递之后修改了在线简历；企业看到的仍是投递时快照 */
    private Boolean resumeUpdatedAfterApply = false;
    private List<SkillVO> skills = new ArrayList<>();
    private List<ApplicationLogVO> logs = new ArrayList<>();
    private List<InterviewVO> interviews = new ArrayList<>();
}
