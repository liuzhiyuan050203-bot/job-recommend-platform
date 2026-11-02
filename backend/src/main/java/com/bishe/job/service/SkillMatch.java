package com.bishe.job.service;

import com.bishe.job.vo.CandidateSkillVO;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 候选人与职位的技能匹配分。
 *
 * <p>职位每个技能标签记 1 份，候选人有该技能时按熟练度给分：入门 0.6、掌握 0.7、熟悉 0.8、熟练 0.9、精通 1.0，
 * 没有记 0；匹配分 = 得分之和 / 职位技能数 × 100，四舍五入。职位没有技能标签时不打分（null），
 * 避免给出看似精确、其实没有依据的数字。</p>
 */
public final class SkillMatch {

    public static final String[] LEVEL_NAMES = {"入门", "掌握", "熟悉", "熟练", "精通"};

    private SkillMatch() {
    }

    public record Result(List<CandidateSkillVO> skills, List<String> missing, int matched, int jobSkillCount, Integer score) {
    }

    /**
     * @param studentSkills 候选人技能：tagId → (名称, 熟练度)
     * @param jobTags       职位技能：tagId → 名称（有序）
     */
    public static Result of(Map<Long, Map.Entry<String, Integer>> studentSkills, LinkedHashMap<Long, String> jobTags) {
        List<CandidateSkillVO> skills = new ArrayList<>();
        double credit = 0;
        int matched = 0;
        for (Map.Entry<Long, Map.Entry<String, Integer>> e : studentSkills.entrySet()) {
            int level = clamp(e.getValue().getValue());
            boolean hit = jobTags.containsKey(e.getKey());
            if (hit) {
                matched++;
                credit += credit(level);
            }
            skills.add(new CandidateSkillVO(e.getKey(), e.getValue().getKey(), level, LEVEL_NAMES[level - 1], hit));
        }
        skills.sort(Comparator.comparing(CandidateSkillVO::getMatched).reversed()
                .thenComparing(CandidateSkillVO::getProficiency, Comparator.reverseOrder()));
        List<String> missing = new ArrayList<>();
        jobTags.forEach((id, name) -> {
            if (!studentSkills.containsKey(id)) {
                missing.add(name);
            }
        });
        Integer score = jobTags.isEmpty() ? null : (int) Math.round(credit / jobTags.size() * 100);
        return new Result(skills, missing, matched, jobTags.size(), score);
    }

    static double credit(int level) {
        return 0.5 + 0.1 * clamp(level);
    }

    private static int clamp(Integer level) {
        if (level == null) {
            return 3;
        }
        return Math.max(1, Math.min(5, level));
    }
}
