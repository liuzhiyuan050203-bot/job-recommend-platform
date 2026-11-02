package com.bishe.job.service;

import com.bishe.job.vo.CandidateSkillVO;
import org.junit.jupiter.api.Test;

import java.util.AbstractMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SkillMatchTest {

    private static LinkedHashMap<Long, String> job(Object... kv) {
        LinkedHashMap<Long, String> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) {
            m.put(((Number) kv[i]).longValue(), (String) kv[i + 1]);
        }
        return m;
    }

    private static Map<Long, Map.Entry<String, Integer>> stu(Object... kv) {
        Map<Long, Map.Entry<String, Integer>> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 3) {
            m.put(((Number) kv[i]).longValue(), new AbstractMap.SimpleEntry<>((String) kv[i + 1], (Integer) kv[i + 2]));
        }
        return m;
    }

    @Test
    void scoresByProficiencyAndCoverage() {
        // 职位 3 个技能：Java 精通(1.0) + MySQL 入门(0.6) + Redis 缺失(0) → 1.6/3 = 53
        SkillMatch.Result r = SkillMatch.of(stu(1, "Java", 5, 3, "MySQL", 1, 9, "Python", 4),
                job(1, "Java", 3, "MySQL", 4, "Redis"));
        assertEquals(53, r.score());
        assertEquals(2, r.matched());
        assertEquals(3, r.jobSkillCount());
        assertEquals(List.of("Redis"), r.missing());
        // 命中的排前面，且熟练度文字正确
        List<CandidateSkillVO> skills = r.skills();
        assertTrue(skills.get(0).getMatched());
        assertEquals("精通", skills.get(0).getProficiencyName());
        assertTrue(skills.get(1).getMatched());
        assertEquals("入门", skills.get(1).getProficiencyName());
        assertFalse(skills.get(2).getMatched());
        assertEquals("Python", skills.get(2).getTagName());
    }

    @Test
    void fullCoverageAtTopLevelIs100AndNoSkillsIsZero() {
        assertEquals(100, SkillMatch.of(stu(1, "Java", 5), job(1, "Java")).score());
        assertEquals(0, SkillMatch.of(stu(), job(1, "Java")).score());
    }

    @Test
    void jobWithoutTagsHasNoScore() {
        SkillMatch.Result r = SkillMatch.of(stu(1, "Java", 3), job());
        assertNull(r.score());
        assertFalse(r.skills().get(0).getMatched());
    }

    @Test
    void outOfRangeProficiencyIsClamped() {
        SkillMatch.Result r = SkillMatch.of(stu(1, "Java", 9, 2, "SQL", null), job(1, "Java", 2, "SQL"));
        assertEquals("精通", r.skills().get(0).getProficiencyName());
        assertEquals(90, r.score()); // (1.0 + 0.8) / 2
    }
}
