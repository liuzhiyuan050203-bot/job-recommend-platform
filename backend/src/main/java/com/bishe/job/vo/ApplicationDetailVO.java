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
    private List<SkillVO> skills = new ArrayList<>();
    private List<ApplicationLogVO> logs = new ArrayList<>();
    private List<InterviewVO> interviews = new ArrayList<>();
}
