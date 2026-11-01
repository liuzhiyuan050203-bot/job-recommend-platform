package com.bishe.job.controller;

import com.bishe.job.common.Result;
import com.bishe.job.dto.ResumeSkillMergeDTO;
import com.bishe.job.service.ResumeFileService;
import com.bishe.job.vo.ResumeParseVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * 学生上传简历原件并选择要并入档案的技能。
 */
@RestController
@RequestMapping("/api/student/resume")
@RequiredArgsConstructor
public class StudentResumeFileController {

    private final ResumeFileService resumeFileService;

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Result<ResumeParseVO> upload(@RequestParam("file") MultipartFile file) {
        return Result.success("解析完成", resumeFileService.upload(file));
    }

    @PostMapping("/skills")
    public Result<Void> merge(@Valid @RequestBody ResumeSkillMergeDTO dto) {
        resumeFileService.mergeSkills(dto.getTagIds());
        resumeFileService.refreshRecommend();
        return Result.success("已合并到我的技能", null);
    }
}
