package com.bishe.job.vo;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/** 候选人技能：熟练度与是否命中所投职位的技能标签。 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class CandidateSkillVO {
    private Long tagId;
    private String tagName;
    private Integer proficiency;
    private String proficiencyName;
    private Boolean matched;
}
