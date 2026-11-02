package com.bishe.job.service;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ResumeSkillSyncTest {

    @Test
    void detectsTestTitles() {
        assertTrue(ResumeSkillSync.isTestTitle("UX-IDOR-简历"));
        assertTrue(ResumeSkillSync.isTestTitle("越权隔离测试简历"));
        assertTrue(ResumeSkillSync.isTestTitle("推荐测试简历1793"));
        assertTrue(ResumeSkillSync.isTestTitle("流程测试简历"));
        assertFalse(ResumeSkillSync.isTestTitle("陈晓-校招简历"));
        assertFalse(ResumeSkillSync.isTestTitle("我的正式简历"));
    }

    @Test
    void mergesSkillDescWithoutDuplicating() {
        assertEquals("Java、Spring Boot、MySQL。",
                ResumeSkillSync.mergeSkillDesc("", List.of("Java", "Spring Boot", "MySQL")));
        assertEquals("Java、Spring Boot、MySQL、Vue。",
                ResumeSkillSync.mergeSkillDesc("Java、Spring Boot、MySQL。", List.of("Java", "Vue")));
        assertEquals("Java、Spring Boot。",
                ResumeSkillSync.mergeSkillDesc("Java、Spring Boot。", List.of("java", "Spring Boot")));
        assertEquals("Spark 入门、Python。",
                ResumeSkillSync.mergeSkillDesc("Spark 入门。", List.of("Spark", "Python")));
    }

    @Test
    void campusTitlePrefersRealName() {
        assertEquals("陈晓-校招简历", ResumeSkillSync.campusResumeTitle("陈晓", "昵称"));
        assertEquals("昵称-校招简历", ResumeSkillSync.campusResumeTitle("  ", "昵称"));
        assertEquals("我的-校招简历", ResumeSkillSync.campusResumeTitle(null, null));
    }
}
