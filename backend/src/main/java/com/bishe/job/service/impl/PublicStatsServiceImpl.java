package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.client.FastApiClient;
import com.bishe.job.common.BusinessException;
import com.bishe.job.entity.SparkRegionDist;
import com.bishe.job.entity.SparkSalaryStat;
import com.bishe.job.entity.SparkTaskLog;
import com.bishe.job.entity.SparkTechTrend;
import com.bishe.job.mapper.SparkRegionDistMapper;
import com.bishe.job.mapper.SparkSalaryStatMapper;
import com.bishe.job.mapper.SparkTaskLogMapper;
import com.bishe.job.mapper.SparkTechTrendMapper;
import com.bishe.job.mapper.StatsQueryMapper;
import com.bishe.job.service.PublicStatsService;
import com.bishe.job.vo.DashboardAggVO;
import com.bishe.job.vo.HiringDemandVO;
import com.bishe.job.vo.RegionPointVO;
import com.bishe.job.vo.SalaryPredictVO;
import com.bishe.job.vo.SalaryStatsVO;
import com.bishe.job.vo.StatsOverviewVO;
import com.bishe.job.vo.TechTrendVO;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Function;

@Service
@RequiredArgsConstructor
public class PublicStatsServiceImpl implements PublicStatsService {

    private final StatsQueryMapper statsQueryMapper;
    private final SparkSalaryStatMapper salaryStatMapper;
    private final SparkTechTrendMapper techTrendMapper;
    private final SparkRegionDistMapper regionDistMapper;
    private final SparkTaskLogMapper taskLogMapper;
    private final FastApiClient fastApiClient;
    private final ObjectMapper objectMapper;

    @Override
    public StatsOverviewVO overview() {
        StatsOverviewVO vo = new StatsOverviewVO();
        vo.setJobCount(statsQueryMapper.countApprovedJobs());
        vo.setCompanyCount(statsQueryMapper.countApprovedCompanies());
        vo.setStudentCount(statsQueryMapper.countActiveStudents());
        vo.setApplicationCount(statsQueryMapper.countApplications());
        List<SparkSalaryStat> salaryRows = latestSalary(null, null);
        if (salaryRows.isEmpty()) {
            vo.setAvgSalary(scale(statsQueryMapper.avgApprovedSalary()));
            vo.setCityCount(statsQueryMapper.countJobCities());
        } else {
            vo.setAvgSalary(weighted(salaryRows, SparkSalaryStat::getAvgSalary));
            vo.setCityCount(salaryRows.stream().map(SparkSalaryStat::getCity).filter(StringUtils::hasText).distinct().count());
        }
        SparkTaskLog latest = latestSuccess("aggregate");
        if (latest == null) {
            latest = latestSuccess(null);
        }
        if (latest != null) {
            vo.setLastBatchNo(latest.getBatchNo());
            vo.setLastSuccessTime(latest.getEndTime() != null ? latest.getEndTime() : latest.getStartTime());
        }
        return vo;
    }

    @Override
    public SalaryStatsVO salary(String city, String techDirection) {
        List<SparkSalaryStat> rows = latestSalary(city, techDirection);
        SalaryStatsVO vo = new SalaryStatsVO();
        List<SalaryStatsVO.SalaryStatItemVO> records = new ArrayList<>();
        for (SparkSalaryStat row : rows) {
            records.add(itemOf(row));
        }
        records.sort(Comparator.comparing(SalaryStatsVO.SalaryStatItemVO::getCity, Comparator.nullsLast(String::compareTo))
                .thenComparing(SalaryStatsVO.SalaryStatItemVO::getTechDirection, Comparator.nullsLast(String::compareTo)));
        vo.setRecords(records);
        vo.setByDirection(rollup(rows, SparkSalaryStat::getTechDirection, true));
        vo.setByCity(rollup(rows, SparkSalaryStat::getCity, false));
        return vo;
    }

    @Override
    public TechTrendVO techTrend(Integer top, Integer months) {
        int topN = top == null || top < 1 ? 10 : Math.min(top, 30);
        int monthN = months == null || months < 1 ? 12 : Math.min(months, 36);
        List<SparkTechTrend> rows = techTrendMapper.selectList(new LambdaQueryWrapper<SparkTechTrend>()
                .eq(SparkTechTrend::getIsLatest, 1)
                .orderByAsc(SparkTechTrend::getStatMonth)
                .orderByAsc(SparkTechTrend::getTagName));
        TechTrendVO vo = new TechTrendVO();
        if (rows.isEmpty()) {
            return vo;
        }
        List<String> allMonths = rows.stream().map(SparkTechTrend::getStatMonth).distinct().sorted().toList();
        List<String> window = allMonths.size() <= monthN ? allMonths : allMonths.subList(allMonths.size() - monthN, allMonths.size());
        vo.setMonths(new ArrayList<>(window));
        Map<String, List<SparkTechTrend>> byTag = new LinkedHashMap<>();
        for (SparkTechTrend row : rows) {
            if (!window.contains(row.getStatMonth())) {
                continue;
            }
            byTag.computeIfAbsent(row.getTagName(), key -> new ArrayList<>()).add(row);
        }
        List<TechTrendVO.RankVO> ranking = new ArrayList<>();
        for (Map.Entry<String, List<SparkTechTrend>> entry : byTag.entrySet()) {
            TechTrendVO.RankVO rank = new TechTrendVO.RankVO();
            rank.setTagName(entry.getKey());
            rank.setTechDirection(entry.getValue().get(entry.getValue().size() - 1).getTechDirection());
            int demand = entry.getValue().stream().mapToInt(item -> item.getDemandCount() == null ? 0 : item.getDemandCount()).sum();
            rank.setDemandCount(demand);
            rank.setAvgSalary(weightedTrend(entry.getValue()));
            ranking.add(rank);
        }
        ranking.sort(Comparator.comparing(TechTrendVO.RankVO::getDemandCount, Comparator.nullsLast(Comparator.reverseOrder()))
                .thenComparing(TechTrendVO.RankVO::getTagName, Comparator.nullsLast(String::compareTo)));
        if (ranking.size() > topN) {
            ranking = new ArrayList<>(ranking.subList(0, topN));
        }
        vo.setRanking(ranking);
        List<TechTrendVO.SeriesVO> series = new ArrayList<>();
        for (TechTrendVO.RankVO rank : ranking) {
            Map<String, Integer> demandByMonth = new LinkedHashMap<>();
            for (SparkTechTrend row : byTag.getOrDefault(rank.getTagName(), List.of())) {
                demandByMonth.put(row.getStatMonth(), row.getDemandCount() == null ? 0 : row.getDemandCount());
            }
            TechTrendVO.SeriesVO item = new TechTrendVO.SeriesVO();
            item.setName(rank.getTagName());
            List<Integer> data = new ArrayList<>();
            for (String month : window) {
                data.add(demandByMonth.getOrDefault(month, 0));
            }
            item.setData(data);
            series.add(item);
        }
        vo.setSeries(series);
        return vo;
    }

    @Override
    public List<RegionPointVO> region() {
        List<SparkRegionDist> rows = regionDistMapper.selectList(new LambdaQueryWrapper<SparkRegionDist>()
                .eq(SparkRegionDist::getIsLatest, 1)
                .orderByDesc(SparkRegionDist::getJobCount));
        List<RegionPointVO> points = new ArrayList<>();
        for (SparkRegionDist row : rows) {
            RegionPointVO vo = new RegionPointVO();
            vo.setName(row.getProvinceName());
            vo.setValue(row.getJobCount());
            vo.setAdcode(row.getAdcode());
            vo.setCompanyCount(row.getCompanyCount());
            vo.setAvgSalary(row.getAvgSalary());
            vo.setApplyCount(row.getApplyCount());
            points.add(vo);
        }
        return points;
    }

    @Override
    public HiringDemandVO hiringDemand(Integer months) {
        int monthN = months == null || months < 1 ? 12 : Math.min(months, 36);
        YearMonth end = YearMonth.now();
        YearMonth start = end.minusMonths(monthN - 1L);
        LocalDateTime startTime = start.atDay(1).atStartOfDay();
        LocalDateTime endTime = end.plusMonths(1).atDay(1).atStartOfDay();
        Map<String, Long> jobs = toMonthMap(statsQueryMapper.monthlyApprovedJobs(startTime, endTime));
        Map<String, Long> applies = toMonthMap(statsQueryMapper.monthlyApplications(startTime, endTime));
        HiringDemandVO vo = new HiringDemandVO();
        for (YearMonth cursor = start; !cursor.isAfter(end); cursor = cursor.plusMonths(1)) {
            String key = cursor.toString();
            vo.getMonths().add(key);
            vo.getJobCounts().add(jobs.getOrDefault(key, 0L));
            vo.getApplyCounts().add(applies.getOrDefault(key, 0L));
        }
        return vo;
    }

    @Override
    public SalaryPredictVO predict(String city, String techDirection, Integer education,
                                   BigDecimal experienceYears, String skills) {
        if (!StringUtils.hasText(city)) {
            throw new BusinessException(400, "城市不能为空");
        }
        if (!StringUtils.hasText(techDirection)) {
            throw new BusinessException(400, "技术方向不能为空");
        }
        if (education == null || education < 1 || education > 4) {
            throw new BusinessException(400, "学历取值应为1到4");
        }
        if (experienceYears == null
                || experienceYears.compareTo(BigDecimal.ZERO) < 0
                || experienceYears.compareTo(new BigDecimal("40")) > 0) {
            throw new BusinessException(400, "工作年限不合法");
        }
        if (skills != null && skills.length() > 200) {
            throw new BusinessException(400, "技能参数过长");
        }
        JsonNode data = fastApiClient.predictSalary(city.trim(), techDirection.trim(), education, experienceYears, skills);
        try {
            return objectMapper.convertValue(data, SalaryPredictVO.class);
        } catch (IllegalArgumentException e) {
            throw new BusinessException(503, "分析服务不可用");
        }
    }

    private List<SparkSalaryStat> latestSalary(String city, String techDirection) {
        LambdaQueryWrapper<SparkSalaryStat> wrapper = new LambdaQueryWrapper<SparkSalaryStat>()
                .eq(SparkSalaryStat::getIsLatest, 1);
        if (StringUtils.hasText(city)) {
            wrapper.eq(SparkSalaryStat::getCity, city.trim());
        }
        if (StringUtils.hasText(techDirection)) {
            wrapper.eq(SparkSalaryStat::getTechDirection, techDirection.trim());
        }
        wrapper.orderByAsc(SparkSalaryStat::getCity).orderByAsc(SparkSalaryStat::getTechDirection);
        return salaryStatMapper.selectList(wrapper);
    }

    private SparkTaskLog latestSuccess(String taskCode) {
        LambdaQueryWrapper<SparkTaskLog> wrapper = new LambdaQueryWrapper<SparkTaskLog>()
                .eq(SparkTaskLog::getStatus, 1)
                .orderByDesc(SparkTaskLog::getId);
        if (StringUtils.hasText(taskCode)) {
            wrapper.eq(SparkTaskLog::getTaskCode, taskCode);
        }
        Page<SparkTaskLog> page = new Page<>(1, 1);
        taskLogMapper.selectPage(page, wrapper);
        if (page.getRecords().isEmpty()) {
            return null;
        }
        return page.getRecords().get(0);
    }

    private SalaryStatsVO.SalaryStatItemVO itemOf(SparkSalaryStat row) {
        SalaryStatsVO.SalaryStatItemVO vo = new SalaryStatsVO.SalaryStatItemVO();
        vo.setProvince(row.getProvince());
        vo.setCity(row.getCity());
        vo.setTechDirection(row.getTechDirection());
        vo.setJobCount(row.getJobCount());
        vo.setAvgSalary(row.getAvgSalary());
        vo.setMedianSalary(row.getMedianSalary());
        vo.setMinSalary(row.getMinSalary());
        vo.setMaxSalary(row.getMaxSalary());
        vo.setP25Salary(row.getP25Salary());
        vo.setP75Salary(row.getP75Salary());
        return vo;
    }

    private List<SalaryStatsVO.SalaryStatItemVO> rollup(List<SparkSalaryStat> rows,
                                                         Function<SparkSalaryStat, String> keyGetter,
                                                         boolean byDirection) {
        Map<String, List<SparkSalaryStat>> grouped = new LinkedHashMap<>();
        for (SparkSalaryStat row : rows) {
            String key = keyGetter.apply(row);
            if (!StringUtils.hasText(key)) {
                continue;
            }
            grouped.computeIfAbsent(key, ignored -> new ArrayList<>()).add(row);
        }
        List<SalaryStatsVO.SalaryStatItemVO> result = new ArrayList<>();
        for (Map.Entry<String, List<SparkSalaryStat>> entry : grouped.entrySet()) {
            List<SparkSalaryStat> group = entry.getValue();
            SalaryStatsVO.SalaryStatItemVO vo = new SalaryStatsVO.SalaryStatItemVO();
            if (byDirection) {
                vo.setTechDirection(entry.getKey());
            } else {
                vo.setCity(entry.getKey());
                vo.setProvince(group.stream().map(SparkSalaryStat::getProvince).filter(StringUtils::hasText).findFirst().orElse(null));
            }
            int jobs = group.stream().mapToInt(item -> item.getJobCount() == null ? 0 : item.getJobCount()).sum();
            vo.setJobCount(jobs);
            vo.setAvgSalary(weighted(group, SparkSalaryStat::getAvgSalary));
            vo.setMedianSalary(weighted(group, SparkSalaryStat::getMedianSalary));
            vo.setP25Salary(weighted(group, SparkSalaryStat::getP25Salary));
            vo.setP75Salary(weighted(group, SparkSalaryStat::getP75Salary));
            vo.setMinSalary(group.stream().map(SparkSalaryStat::getMinSalary).filter(Objects::nonNull).min(Comparator.naturalOrder()).orElse(null));
            vo.setMaxSalary(group.stream().map(SparkSalaryStat::getMaxSalary).filter(Objects::nonNull).max(Comparator.naturalOrder()).orElse(null));
            result.add(vo);
        }
        result.sort(Comparator.comparing(SalaryStatsVO.SalaryStatItemVO::getAvgSalary, Comparator.nullsLast(Comparator.reverseOrder())));
        return result;
    }

    private BigDecimal weighted(List<SparkSalaryStat> rows, Function<SparkSalaryStat, BigDecimal> getter) {
        BigDecimal sum = BigDecimal.ZERO;
        long weight = 0;
        for (SparkSalaryStat row : rows) {
            BigDecimal value = getter.apply(row);
            int count = row.getJobCount() == null ? 0 : row.getJobCount();
            if (value == null || count <= 0) {
                continue;
            }
            sum = sum.add(value.multiply(BigDecimal.valueOf(count)));
            weight += count;
        }
        if (weight == 0) {
            return null;
        }
        return sum.divide(BigDecimal.valueOf(weight), 2, RoundingMode.HALF_UP);
    }

    private BigDecimal weightedTrend(List<SparkTechTrend> rows) {
        BigDecimal sum = BigDecimal.ZERO;
        long weight = 0;
        for (SparkTechTrend row : rows) {
            if (row.getAvgSalary() == null || row.getDemandCount() == null || row.getDemandCount() <= 0) {
                continue;
            }
            sum = sum.add(row.getAvgSalary().multiply(BigDecimal.valueOf(row.getDemandCount())));
            weight += row.getDemandCount();
        }
        if (weight == 0) {
            return null;
        }
        return sum.divide(BigDecimal.valueOf(weight), 2, RoundingMode.HALF_UP);
    }

    private Map<String, Long> toMonthMap(List<DashboardAggVO> rows) {
        Map<String, Long> map = new LinkedHashMap<>();
        if (rows == null) {
            return map;
        }
        for (DashboardAggVO row : rows) {
            if (row == null || !StringUtils.hasText(row.getLabel())) {
                continue;
            }
            map.put(row.getLabel().trim(), row.getTotal() == null ? 0L : row.getTotal());
        }
        return map;
    }

    private BigDecimal scale(BigDecimal value) {
        if (value == null) {
            return null;
        }
        return value.setScale(2, RoundingMode.HALF_UP);
    }
}
