package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.PublicJobQuery;
import com.bishe.job.service.PublicJobService;
import com.bishe.job.service.RecommendService;
import com.bishe.job.vo.PublicJobVO;
import com.bishe.job.vo.SimilarJobVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/public/jobs")
@RequiredArgsConstructor
public class PublicJobController {

    private final PublicJobService publicJobService;
    private final RecommendService recommendService;

    @GetMapping
    public Result<PageResult<PublicJobVO>> search(
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "techDirection", required = false) String techDirection,
            @RequestParam(value = "categoryId", required = false) Long categoryId,
            @RequestParam(value = "city", required = false) String city,
            @RequestParam(value = "salaryMin", required = false) Integer salaryMin,
            @RequestParam(value = "salaryMax", required = false) Integer salaryMax,
            @RequestParam(value = "education", required = false) Integer education,
            @RequestParam(value = "jobType", required = false) Integer jobType,
            @RequestParam(value = "tagIds", required = false) List<String> tagIds,
            @RequestParam(value = "sort", required = false) String sort,
            @RequestParam(value = "source", required = false) String source,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        PublicJobQuery query = new PublicJobQuery();
        query.setKeyword(keyword);
        query.setTechDirection(techDirection);
        query.setCategoryId(categoryId);
        query.setCity(city);
        query.setSalaryMin(salaryMin);
        query.setSalaryMax(salaryMax);
        query.setEducation(education);
        query.setJobType(jobType);
        query.setTagIds(publicJobService.parseTagIds(tagIds));
        query.setSort(sort);
        query.setSource(source);
        return Result.success(publicJobService.search(query, current, size));
    }

    @GetMapping("/{id}")
    public Result<PublicJobVO> detail(@PathVariable("id") Long id) {
        return Result.success(publicJobService.detail(id));
    }

    @GetMapping("/{id}/similar")
    public Result<List<SimilarJobVO>> similar(
            @PathVariable("id") Long id,
            @RequestParam(value = "size", defaultValue = "6") long size) {
        return Result.success(recommendService.similarJobs(id, size));
    }
}
