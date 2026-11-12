package com.bishe.job.service;

import com.bishe.job.entity.JobApplicationResume;
import com.bishe.job.entity.StuResume;
import com.bishe.job.vo.ResumeVO;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDateTime;
import java.util.HexFormat;

/**
 * 投递简历快照：字段拷贝、内容哈希（与 phase8 回填 SQL 的 SHA2(CONCAT_WS(CHAR(1), ...)) 一致）。
 */
public final class ResumeSnapshots {

    static final char SEP = 0x01;

    private ResumeSnapshots() {
    }

    public static String hash(String title, String educationExp, String projectExp, String internshipExp,
                              String skillDesc, String selfEvaluation, String attachmentUrl) {
        String raw = String.join(String.valueOf(SEP),
                nz(title), nz(educationExp), nz(projectExp), nz(internshipExp),
                nz(skillDesc), nz(selfEvaluation), nz(attachmentUrl));
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(raw.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 不可用", ex);
        }
    }

    public static String hash(StuResume resume) {
        if (resume == null) {
            return hash("", "", "", "", "", "", "");
        }
        return hash(resume.getTitle(), resume.getEducationExp(), resume.getProjectExp(),
                resume.getInternshipExp(), resume.getSkillDesc(), resume.getSelfEvaluation(),
                resume.getAttachmentUrl());
    }

    public static String hash(JobApplicationResume snapshot) {
        if (snapshot == null) {
            return hash("", "", "", "", "", "", "");
        }
        return hash(snapshot.getTitle(), snapshot.getEducationExp(), snapshot.getProjectExp(),
                snapshot.getInternshipExp(), snapshot.getSkillDesc(), snapshot.getSelfEvaluation(),
                snapshot.getAttachmentUrl());
    }

    public static boolean sameContent(StuResume current, JobApplicationResume snapshot) {
        if (current == null || snapshot == null) {
            return false;
        }
        return hash(current).equalsIgnoreCase(hash(snapshot));
    }

    public static JobApplicationResume fromResume(Long applicationId, StuResume resume, LocalDateTime capturedAt) {
        JobApplicationResume row = new JobApplicationResume();
        row.setApplicationId(applicationId);
        if (resume != null) {
            row.setResumeId(resume.getId());
            row.setTitle(nz(resume.getTitle()));
            row.setEducationExp(resume.getEducationExp());
            row.setProjectExp(resume.getProjectExp());
            row.setInternshipExp(resume.getInternshipExp());
            row.setSkillDesc(resume.getSkillDesc());
            row.setSelfEvaluation(resume.getSelfEvaluation());
            row.setAttachmentUrl(resume.getAttachmentUrl());
            row.setContentHash(hash(resume));
        } else {
            row.setTitle("");
            row.setContentHash(hash("", "", "", "", "", "", ""));
        }
        row.setCapturedAt(capturedAt == null ? LocalDateTime.now() : capturedAt);
        return row;
    }

    public static ResumeVO toResumeVo(JobApplicationResume snapshot) {
        ResumeVO vo = new ResumeVO();
        if (snapshot == null) {
            return vo;
        }
        vo.setId(snapshot.getResumeId());
        vo.setTitle(snapshot.getTitle());
        vo.setEducationExp(snapshot.getEducationExp());
        vo.setProjectExp(snapshot.getProjectExp());
        vo.setInternshipExp(snapshot.getInternshipExp());
        vo.setSkillDesc(snapshot.getSkillDesc());
        vo.setSelfEvaluation(snapshot.getSelfEvaluation());
        vo.setAttachmentUrl(snapshot.getAttachmentUrl());
        vo.setUpdateTime(snapshot.getCapturedAt());
        vo.setCreateTime(snapshot.getCapturedAt());
        return vo;
    }

    static String nz(String value) {
        return value == null ? "" : value;
    }
}
