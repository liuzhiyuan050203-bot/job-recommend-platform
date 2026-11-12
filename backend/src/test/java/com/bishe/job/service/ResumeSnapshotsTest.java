package com.bishe.job.service;

import com.bishe.job.entity.JobApplicationResume;
import com.bishe.job.entity.StuResume;
import com.bishe.job.vo.ResumeVO;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.LocalDateTime;
import java.util.HexFormat;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ResumeSnapshotsTest {

    @Test
    void hashMatchesMysqlSha2ConcatWs() throws Exception {
        // 与迁移脚本 SHA2(CONCAT_WS(CHAR(1), ...), 256) 对齐：空字段当空串，分隔符 0x01
        String raw = String.join(String.valueOf((char) 0x01),
                "校招简历", "测试大学 本科", "在线商城", "", "Java", "认真", "");
        String expected = HexFormat.of().formatHex(
                MessageDigest.getInstance("SHA-256").digest(raw.getBytes(StandardCharsets.UTF_8)));
        assertEquals(expected, ResumeSnapshots.hash("校招简历", "测试大学 本科", "在线商城", "", "Java", "认真", ""));
        assertEquals(64, expected.length());
    }

    @Test
    void nullFieldsHashSameAsEmpty() {
        assertEquals(ResumeSnapshots.hash("", "", "", "", "", "", ""),
                ResumeSnapshots.hash(null, null, null, null, null, null, null));
    }

    @Test
    void detectsContentChange() {
        StuResume resume = resume("校招简历", "项目A");
        JobApplicationResume snapshot = ResumeSnapshots.fromResume(1L, resume, LocalDateTime.of(2026, 11, 12, 10, 0));
        assertTrue(ResumeSnapshots.sameContent(resume, snapshot));
        resume.setProjectExp("项目B");
        assertFalse(ResumeSnapshots.sameContent(resume, snapshot));
        assertEquals(snapshot.getContentHash(), ResumeSnapshots.hash(
                "校招简历", "教育", "项目A", "实习", "Java", "评价", "1/abc.pdf"));
    }

    @Test
    void fromResumeAndToVoCopyFields() {
        StuResume resume = resume("投递简历", "商城后端");
        resume.setId(9L);
        resume.setUserId(3L);
        LocalDateTime at = LocalDateTime.of(2026, 11, 1, 8, 30, 0);
        JobApplicationResume snapshot = ResumeSnapshots.fromResume(42L, resume, at);
        assertEquals(42L, snapshot.getApplicationId());
        assertEquals(9L, snapshot.getResumeId());
        assertEquals(at, snapshot.getCapturedAt());
        ResumeVO vo = ResumeSnapshots.toResumeVo(snapshot);
        assertEquals(9L, vo.getId());
        assertEquals("投递简历", vo.getTitle());
        assertEquals("商城后端", vo.getProjectExp());
        assertEquals("1/abc.pdf", vo.getAttachmentUrl());
        assertEquals(at, vo.getUpdateTime());
    }

    private static StuResume resume(String title, String project) {
        StuResume resume = new StuResume();
        resume.setTitle(title);
        resume.setEducationExp("教育");
        resume.setProjectExp(project);
        resume.setInternshipExp("实习");
        resume.setSkillDesc("Java");
        resume.setSelfEvaluation("评价");
        resume.setAttachmentUrl("1/abc.pdf");
        return resume;
    }
}
