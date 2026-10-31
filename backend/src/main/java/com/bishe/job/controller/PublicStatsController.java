package com.bishe.job.controller;

import com.bishe.job.common.Result;
import com.bishe.job.service.PublicStatsService;
import com.bishe.job.vo.RegionPointVO;
import com.bishe.job.vo.SalaryPredictVO;
import com.bishe.job.vo.SalaryStatsVO;
import com.bishe.job.vo.StatsOverviewVO;
import com.bishe.job.vo.TechTrendVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigDecimal;
import java.util.List;

@RestController
@RequestMapping("/api/public/stats")
@RequiredArgsConstructor
public class PublicStatsController {

    private final PublicStatsService publicStatsService;

    @GetMapping("/overview")
    public Result<StatsOverviewVO> overview() {
        return Result.success(publicStatsService.overview());
    }

    @GetMapping("/salary")
    public Result<SalaryStatsVO> salary(
            @RequestParam(value = "city", required = false) String city,
            @RequestParam(value = "techDirection", required = false) String techDirection,
            @RequestParam(value = "tech_direction", required = false) String techDirectionSnake) {
        return Result.success(publicStatsService.salary(city, firstText(techDirection, techDirectionSnake)));
    }

    @GetMapping("/tech-trend")
    public Result<TechTrendVO> techTrend(
            @RequestParam(value = "top", required = false) Integer top,
            @RequestParam(value = "months", required = false) Integer months) {
        return Result.success(publicStatsService.techTrend(top, months));
    }

    @GetMapping("/region")
    public Result<List<RegionPointVO>> region() {
        return Result.success(publicStatsService.region());
    }

    @GetMapping("/salary/predict")
    public Result<SalaryPredictVO> predict(
            @RequestParam(value = "city", required = false) String city,
            @RequestParam(value = "techDirection", required = false) String techDirection,
            @RequestParam(value = "tech_direction", required = false) String techDirectionSnake,
            @RequestParam(value = "education", required = false) Integer education,
            @RequestParam(value = "experienceYears", required = false) BigDecimal experienceYears,
            @RequestParam(value = "experience_years", required = false) BigDecimal experienceYearsSnake,
            @RequestParam(value = "skills", required = false) String skills) {
        BigDecimal years = experienceYears != null ? experienceYears : experienceYearsSnake;
        return Result.success(publicStatsService.predict(city, firstText(techDirection, techDirectionSnake), education, years, skills));
    }

    private String firstText(String primary, String secondary) {
        if (primary != null && !primary.isBlank()) {
            return primary;
        }
        if (secondary != null && !secondary.isBlank()) {
            return secondary;
        }
        return null;
    }
}
