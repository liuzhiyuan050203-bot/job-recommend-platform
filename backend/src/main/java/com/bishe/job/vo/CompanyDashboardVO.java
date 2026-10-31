package com.bishe.job.vo;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

/**
 * 企业招聘看板。applicantSkills 为投递者技能标签出现人数，最多 15 个。
 */
@Data
public class CompanyDashboardVO {

    private List<JobItemVO> jobs = new ArrayList<>();
    private List<StatusCountVO> applicationStatus = new ArrayList<>();
    private List<SkillCountVO> applicantSkills = new ArrayList<>();

    @Data
    public static class JobItemVO {
        private Long positionId;
        private String title;
        private Integer viewCount;
        private Integer favoriteCount;
        private Integer applyCount;
        private Integer shelfStatus;
    }

    @Data
    public static class StatusCountVO {
        private Integer status;
        private String label;
        private long count;
    }

    @Data
    public static class SkillCountVO {
        private String name;
        private long count;
    }
}
