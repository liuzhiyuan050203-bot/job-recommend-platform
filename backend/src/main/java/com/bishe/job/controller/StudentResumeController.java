package com.bishe.job.controller;

import com.bishe.job.common.Result;
import com.bishe.job.dto.ResumeSaveDTO;
import com.bishe.job.service.ResumeDownload;
import com.bishe.job.service.ResumeFileService;
import com.bishe.job.service.StudentResumeService;
import com.bishe.job.vo.ResumeVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/student/resumes")
@RequiredArgsConstructor
public class StudentResumeController {

    private final StudentResumeService studentResumeService;
    private final ResumeFileService resumeFileService;

    @GetMapping
    public Result<List<ResumeVO>> list() {
        return Result.success(studentResumeService.list());
    }

    @GetMapping("/{id}")
    public Result<ResumeVO> detail(@PathVariable("id") Long id) {
        return Result.success(studentResumeService.detail(id));
    }

    @PostMapping
    public Result<ResumeVO> create(@Valid @RequestBody ResumeSaveDTO dto) {
        return Result.success("简历已创建", studentResumeService.create(dto));
    }

    @PutMapping("/{id}")
    public Result<ResumeVO> update(@PathVariable("id") Long id, @Valid @RequestBody ResumeSaveDTO dto) {
        return Result.success("简历已保存", studentResumeService.update(id, dto));
    }

    @PutMapping("/{id}/default")
    public Result<Void> setDefault(@PathVariable("id") Long id) {
        studentResumeService.setDefault(id);
        return Result.success("已设为默认简历", null);
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable("id") Long id) {
        studentResumeService.delete(id);
        return Result.success("简历已删除", null);
    }

    @GetMapping("/{id}/file")
    public ResponseEntity<byte[]> file(@PathVariable("id") Long id) {
        return attachment(resumeFileService.downloadOwn(id));
    }

    static ResponseEntity<byte[]> attachment(ResumeDownload file) {
        ContentDisposition disposition = ContentDisposition.attachment()
                .filename(file.filename())
                .build();
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, disposition.toString())
                .header("X-Content-Type-Options", "nosniff")
                .contentType(MediaType.parseMediaType(file.contentType()))
                .contentLength(file.bytes().length)
                .body(file.bytes());
    }
}
