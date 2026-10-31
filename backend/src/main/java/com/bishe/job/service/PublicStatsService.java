package com.bishe.job.service;

import com.bishe.job.vo.RegionPointVO;
import com.bishe.job.vo.SalaryPredictVO;
import com.bishe.job.vo.SalaryStatsVO;
import com.bishe.job.vo.StatsOverviewVO;
import com.bishe.job.vo.TechTrendVO;

import java.math.BigDecimal;
import java.util.List;

public interface PublicStatsService {

    StatsOverviewVO overview();

    SalaryStatsVO salary(String city, String techDirection);

    TechTrendVO techTrend(Integer top, Integer months);

    List<RegionPointVO> region();

    SalaryPredictVO predict(String city, String techDirection, Integer education, BigDecimal experienceYears, String skills);
}
