package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.FavoriteCreateDTO;
import com.bishe.job.service.StudentFavoriteService;
import com.bishe.job.vo.PublicJobVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/student/favorites")
@RequiredArgsConstructor
public class StudentFavoriteController {

    private final StudentFavoriteService studentFavoriteService;

    @GetMapping
    public Result<PageResult<PublicJobVO>> page(
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(studentFavoriteService.page(current, size));
    }

    @PostMapping
    public Result<Void> add(@Valid @RequestBody FavoriteCreateDTO dto) {
        studentFavoriteService.add(dto.getJobId());
        return Result.success("收藏成功", null);
    }

    @DeleteMapping("/{jobId}")
    public Result<Void> remove(@PathVariable("jobId") Long jobId) {
        studentFavoriteService.remove(jobId);
        return Result.success("已取消收藏", null);
    }
}
