package com.bishe.job.service;

import com.bishe.job.vo.ResumeParseVO;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

public interface ResumeFileService {

    ResumeParseVO upload(MultipartFile file);

    void mergeSkills(List<Long> tagIds);

    /** 技能落库后再调一次实时推荐，失败只记日志，不影响合并结果。 */
    void refreshRecommend();

    ResumeDownload downloadOwn(Long resumeId);

    ResumeDownload downloadForCompany(Long applicationId);
}
