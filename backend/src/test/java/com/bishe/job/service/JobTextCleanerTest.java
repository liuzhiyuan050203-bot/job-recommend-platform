package com.bishe.job.service;

import com.bishe.job.vo.JobSourceVO;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class JobTextCleanerTest {

    private static final String REAL_REQ = "{\"provenance\": {\"company_key\": \"bytedance\", \"company_label\": \"字节跳动\", "
            + "\"source\": \"jobs.bytedance.com\", \"post_id\": \"1\", \"apply_url\": \"https://jobs.bytedance.com/campus/position/1/detail\", "
            + "\"crawled_at\": \"2026-11-01T02:28:57+08:00\", \"recruit_label\": \"正式\", \"project\": \"算法\", \"work_cities\": \"北京 / 上海\"}}";
    private static final String REAL_DESC = "【校招官网投递】https://jobs.bytedance.com/campus/position/1/detail\n"
            + "【来源】jobs.bytedance.com / 字节跳动 / post_id=1\n【项目/方向】算法 / 正式\n【工作城市】北京 / 上海\n"
            + "【抓取时间】2026-11-01T02:28:57+08:00\n\n岗位名称：算法工程师\n"
            + "本条记录由公开校园招聘 API 同步，薪资为平台按方向与城市估算，实际以官网为准。";

    @Test
    void realJobMetadataBecomesSourceNotText() {
        JobTextCleaner.Cleaned c = JobTextCleaner.clean(REAL_DESC, REAL_REQ, "投递链接: https://jobs.bytedance.com/campus/position/1/detail");
        assertTrue(c.requirementItems().isEmpty(), "provenance JSON 不应出现在任职要求里");
        assertTrue(c.descriptionItems().isEmpty(), "抓取元数据不应出现在岗位职责里");
        assertEquals("", c.welfare());
        assertTrue(c.salaryEstimated());
        JobSourceVO s = c.source();
        assertEquals(JobSourceVO.CRAWLER, s.getType());
        assertEquals("字节跳动校招官网", s.getLabel());
        assertEquals("jobs.bytedance.com", s.getSite());
        assertEquals("https://jobs.bytedance.com/campus/position/1/detail", s.getApplyUrl());
        assertEquals("算法", s.getProject());
        assertEquals("北京 / 上海", s.getWorkCities());
    }

    @Test
    void descriptionHeaderAloneStillGivesSource() {
        JobTextCleaner.Cleaned c = JobTextCleaner.clean(REAL_DESC + "\n负责推荐算法研发", "", null);
        assertEquals(List.of("负责推荐算法研发"), c.descriptionItems());
        assertEquals("字节跳动校招官网", c.source().getLabel());
        assertTrue(c.salaryEstimated());
    }

    @Test
    void jsonArrayAndDoubleEncoded() {
        assertEquals(List.of("统招本科及以上学历", "精通Java"),
                JobTextCleaner.clean(null, "[\"1. 统招本科及以上学历\", \"2. 精通Java\"]", null).requirementItems());
        assertEquals(List.of("熟悉 Spring Boot", "了解 Redis"),
                JobTextCleaner.clean(null, "\"[\\\"1、熟悉 Spring Boot\\\", \\\"2、了解 Redis\\\"]\"", null).requirementItems());
        assertEquals(List.of("会 Python", "会 SQL"),
                JobTextCleaner.clean(null, "{\"requirements\": [{\"text\": \"会 Python\"}, \"会 SQL\"], \"source\": \"x.com\", \"salary_estimated\": true}", null).requirementItems());
    }

    @Test
    void brokenJsonFallsBackToReadableText() {
        List<String> items = JobTextCleaner.clean(null, "[\"本科\", \"熟悉 Vue", null).requirementItems();
        assertFalse(items.isEmpty());
        items.forEach(i -> assertFalse(i.contains("\"") || i.contains("[")));
    }

    @Test
    void platformJobKeepsNumberedLines() {
        String desc = "1. 负责测试开发相关功能的设计与编码；\n2. 基于JMeter完成模块开发\\n3. 编写单元测试，保证 3.5 倍覆盖";
        JobTextCleaner.Cleaned c = JobTextCleaner.clean(desc, "1. 本科\n2. 掌握 Pytest", "五险一金、年度体检");
        assertEquals(List.of("负责测试开发相关功能的设计与编码", "基于JMeter完成模块开发", "编写单元测试，保证 3.5 倍覆盖"), c.descriptionItems());
        assertEquals(List.of("本科", "掌握 Pytest"), c.requirementItems());
        assertEquals("五险一金、年度体检", c.welfare());
        assertEquals(JobSourceVO.PLATFORM, c.source().getType());
        assertEquals("企业发布", c.source().getLabel());
        assertFalse(c.salaryEstimated());
    }
}
