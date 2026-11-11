package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.dto.PublicJobQuery;
import com.bishe.job.entity.JobApplication;
import com.bishe.job.entity.JobFavorite;
import com.bishe.job.mapper.JobApplicationMapper;
import com.bishe.job.mapper.JobFavoriteMapper;
import com.bishe.job.mapper.JobPositionMapper;
import com.bishe.job.mapper.JobQueryMapper;
import com.bishe.job.security.LoginUser;
import com.bishe.job.security.RoleCodes;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.BehaviorLogService;
import com.bishe.job.service.JobTextCleaner;
import com.bishe.job.service.PositionTags;
import com.bishe.job.service.PublicJobService;
import com.bishe.job.vo.PositionTagVO;
import com.bishe.job.vo.PublicJobVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
@RequiredArgsConstructor
public class PublicJobServiceImpl implements PublicJobService {

    private final JobQueryMapper jobQueryMapper;
    private final JobPositionMapper jobPositionMapper;
    private final JobFavoriteMapper jobFavoriteMapper;
    private final JobApplicationMapper jobApplicationMapper;
    private final PositionTags positionTags;
    private final BehaviorLogService behaviorLogService;

    @Override
    public PageResult<PublicJobVO> search(PublicJobQuery query, long current, long size) {
        PublicJobQuery safe = normalize(query);
        Page<PublicJobVO> page = Pages.of(current, size);
        jobQueryMapper.searchJobs(page, safe);
        fillTags(page.getRecords());
        fillStudentMarks(page.getRecords());
        page.getRecords().forEach(job -> job.setSalaryEstimated(isEstimatedSource(job.getSourceCode())));
        return PageResult.of(page);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public PublicJobVO detail(Long id) {
        PublicJobVO vo = jobQueryMapper.selectVisible(id);
        if (vo == null) {
            throw new BusinessException(404, "职位不存在或已下架");
        }
        jobPositionMapper.incrView(id);
        vo.setViewCount((vo.getViewCount() == null ? 0 : vo.getViewCount()) + 1);
        fillTags(List.of(vo));
        fillStudentMarks(List.of(vo));
        applyCleanText(vo);
        behaviorLogService.logJob(BehaviorLogService.VIEW, id);
        return vo;
    }

    /** 详情展示用：拆出抓取元数据、估算薪资说明，正文整理成条目。库里原文不动。 */
    static void applyCleanText(PublicJobVO vo) {
        JobTextCleaner.Cleaned cleaned = JobTextCleaner.clean(vo.getDescription(), vo.getRequirement(), vo.getWelfare());
        vo.setDescriptionItems(cleaned.descriptionItems());
        vo.setRequirementItems(cleaned.requirementItems());
        vo.setDescription(String.join("\n", cleaned.descriptionItems()));
        vo.setRequirement(String.join("\n", cleaned.requirementItems()));
        vo.setWelfare(cleaned.welfare());
        vo.setDataSource(cleaned.source());
        boolean estimated = cleaned.salaryEstimated() || isEstimatedSource(vo.getSourceCode());
        vo.setSalaryEstimated(estimated);
        vo.setSalaryNote(estimated ? JobTextCleaner.ESTIMATE_NOTE : null);
        if (EXT_ATS.equals(vo.getSourceCode())) {
            vo.setSalaryNote(EXT_ESTIMATE_NOTE);
        }
        if (EXT_ATS.equals(vo.getSourceCode()) && cleaned.source() != null) {
            String label = cleaned.source().getLabel();
            cleaned.source().setLabel("外部来源 · " + (label == null ? "企业招聘官网" : label.replace("校招官网", "招聘官网")));
        }
    }

    public static final String EXT_ATS = "ext_ats";
    static final String EXT_ESTIMATE_NOTE =
            "该职位为外部来源，同步自企业招聘官网公开信息，官网未公布薪资，此处薪资为平台按技术方向与城市估算，仅供参考；投递请前往企业官网。";

    /** 自爬校招官网与外部扩充库的职位官网都未公布薪资，列表/详情的薪资均为平台估算。 */
    public static boolean isEstimatedSource(String sourceCode) {
        return "self_crawl".equals(sourceCode) || EXT_ATS.equals(sourceCode);
    }

    @Override
    public List<Long> parseTagIds(List<String> raw) {
        if (raw == null || raw.isEmpty()) {
            return List.of();
        }
        List<Long> ids = new ArrayList<>();
        for (String part : raw) {
            if (!StringUtils.hasText(part)) {
                continue;
            }
            for (String piece : part.split(",")) {
                String text = piece.trim();
                if (text.isEmpty()) {
                    continue;
                }
                try {
                    ids.add(Long.valueOf(text));
                } catch (NumberFormatException ex) {
                    throw new BusinessException(400, "技能标签参数不正确");
                }
            }
        }
        return ids.stream().distinct().toList();
    }

    /**
     * 学历：职位 education 小于等于传入值才命中。0 为不限。
     * 排序只接受 newest、salary、hot，其他值一律按最新，不进入 SQL。
     */
    private PublicJobQuery normalize(PublicJobQuery raw) {
        PublicJobQuery query = raw == null ? new PublicJobQuery() : raw;
        query.setKeyword(escapeLike(query.getKeyword()));
        query.setTechDirection(blankToNull(query.getTechDirection()));
        query.setCity(blankToNull(query.getCity()));
        if (query.getEducation() != null && (query.getEducation() < 0 || query.getEducation() > 4)) {
            throw new BusinessException(400, "学历筛选取值不正确");
        }
        if (query.getJobType() != null && (query.getJobType() < 1 || query.getJobType() > 3)) {
            throw new BusinessException(400, "工作性质取值不正确");
        }
        if (query.getSalaryMin() != null && query.getSalaryMin() < 0) {
            throw new BusinessException(400, "薪资筛选取值不正确");
        }
        if (query.getSalaryMax() != null && query.getSalaryMax() < 0) {
            throw new BusinessException(400, "薪资筛选取值不正确");
        }
        if (query.getSalaryMin() != null && query.getSalaryMax() != null && query.getSalaryMin() > query.getSalaryMax()) {
            throw new BusinessException(400, "薪资筛选区间不正确");
        }
        if (query.getTagIds() != null && query.getTagIds().isEmpty()) {
            query.setTagIds(null);
        }
        query.setSort(normalizeSort(query.getSort()));
        query.setSource(normalizeSource(query.getSource()));
        return query;
    }

    /** 来源筛选白名单，其他取值按「全部」处理。 */
    private String normalizeSource(String source) {
        if (!StringUtils.hasText(source)) {
            return null;
        }
        return switch (source.trim()) {
            case "platform", "self_crawl", "ext_ats", "internal" -> source.trim();
            default -> null;
        };
    }

    private String normalizeSort(String sort) {
        if (!StringUtils.hasText(sort)) {
            return "newest";
        }
        return switch (sort.trim()) {
            case "salary", "hot", "newest" -> sort.trim();
            default -> "newest";
        };
    }

    private String escapeLike(String raw) {
        String text = blankToNull(raw);
        if (text == null) {
            return null;
        }
        if (text.length() > 64) {
            text = text.substring(0, 64);
        }
        return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
    }

    private String blankToNull(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        return value.trim();
    }

    private void fillTags(List<PublicJobVO> jobs) {
        if (jobs == null || jobs.isEmpty()) {
            return;
        }
        Map<Long, List<PositionTagVO>> grouped = positionTags.of(jobs.stream().map(PublicJobVO::getId).toList());
        for (PublicJobVO job : jobs) {
            List<PositionTagVO> tags = grouped.getOrDefault(job.getId(), List.of());
            job.setTagIds(tags.stream().map(PositionTagVO::getTagId).toList());
            job.setTagNames(tags.stream().map(PositionTagVO::getTagName).toList());
        }
    }

    private void fillStudentMarks(List<PublicJobVO> jobs) {
        if (jobs == null || jobs.isEmpty()) {
            return;
        }
        LoginUser user = UserContext.get();
        boolean student = user != null && Integer.valueOf(RoleCodes.STUDENT).equals(user.getRole());
        if (!student) {
            for (PublicJobVO job : jobs) {
                job.setFavorited(false);
                job.setApplied(false);
            }
            return;
        }
        List<Long> ids = jobs.stream().map(PublicJobVO::getId).toList();
        Set<Long> favored = new HashSet<>();
        jobFavoriteMapper.selectList(new LambdaQueryWrapper<JobFavorite>()
                        .eq(JobFavorite::getUserId, user.getId())
                        .in(JobFavorite::getPositionId, ids))
                .forEach(row -> favored.add(row.getPositionId()));
        Set<Long> applied = new HashSet<>();
        jobApplicationMapper.selectList(new LambdaQueryWrapper<JobApplication>()
                        .eq(JobApplication::getUserId, user.getId())
                        .in(JobApplication::getPositionId, ids))
                .forEach(row -> applied.add(row.getPositionId()));
        for (PublicJobVO job : jobs) {
            job.setFavorited(favored.contains(job.getId()));
            job.setApplied(applied.contains(job.getId()));
        }
    }
}
