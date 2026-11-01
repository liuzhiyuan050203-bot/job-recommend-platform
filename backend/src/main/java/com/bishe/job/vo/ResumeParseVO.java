package com.bishe.job.vo;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

/**
 * 简历解析结果。skills 是建议，尚未写入 stu_skill。
 */
@Data
public class ResumeParseVO {

    private String textPreview;

    /** 附件挂到的简历编号 */
    private Long resumeId;

    private List<MatchedSkillVO> skills = new ArrayList<>();

    @Data
    public static class MatchedSkillVO {
        private Long tagId;
        private String name;
        private String direction;
        private String evidence;
    }
}
