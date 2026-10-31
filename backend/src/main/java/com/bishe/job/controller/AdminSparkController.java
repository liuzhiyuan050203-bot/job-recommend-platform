package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.SparkRunDTO;
import com.bishe.job.service.SparkAdminService;
import com.bishe.job.vo.SparkRunVO;
import com.bishe.job.vo.SparkTaskLogVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin/spark")
@RequiredArgsConstructor
public class AdminSparkController {

    private final SparkAdminService sparkAdminService;

    @PostMapping("/run")
    public Result<SparkRunVO> run(@RequestBody(required = false) SparkRunDTO dto) {
        return Result.success(sparkAdminService.run(dto == null ? null : dto.getTasks()));
    }

    @GetMapping("/tasks")
    public Result<PageResult<SparkTaskLogVO>> tasks(
            @RequestParam(value = "batchNo", required = false) String batchNo,
            @RequestParam(value = "batch_no", required = false) String batchNoSnake,
            @RequestParam(value = "status", required = false) Integer status,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        String batch = hasText(batchNo) ? batchNo : batchNoSnake;
        return Result.success(sparkAdminService.tasks(batch, status, current, size));
    }

    private boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
