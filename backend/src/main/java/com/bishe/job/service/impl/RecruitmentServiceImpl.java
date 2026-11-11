package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.dto.ApplicationCreateDTO;
import com.bishe.job.dto.ApplicationStatusDTO;
import com.bishe.job.dto.InterviewNoticeDTO;
import com.bishe.job.dto.InterviewResultDTO;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.JobApplication;
import com.bishe.job.entity.JobApplicationLog;
import com.bishe.job.entity.JobInterview;
import com.bishe.job.entity.JobPosition;
import com.bishe.job.entity.SkillTag;
import com.bishe.job.entity.StuProfile;
import com.bishe.job.entity.StuResume;
import com.bishe.job.entity.StuSkill;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.EntCompanyMapper;
import com.bishe.job.mapper.JobApplicationLogMapper;
import com.bishe.job.mapper.JobApplicationMapper;
import com.bishe.job.mapper.JobInterviewMapper;
import com.bishe.job.mapper.JobPositionMapper;
import com.bishe.job.mapper.SkillTagMapper;
import com.bishe.job.mapper.StuProfileMapper;
import com.bishe.job.mapper.StuResumeMapper;
import com.bishe.job.mapper.StuSkillMapper;
import com.bishe.job.mapper.SysUserMapper;
import com.bishe.job.security.RoleCodes;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.ApplicationStateMachine;
import com.bishe.job.service.BehaviorLogService;
import com.bishe.job.service.CompanySupport;
import com.bishe.job.service.PositionTags;
import com.bishe.job.service.RecruitmentService;
import com.bishe.job.service.SkillMatch;
import com.bishe.job.service.VisibleJobSupport;
import com.bishe.job.vo.AdminOverviewVO;
import com.bishe.job.vo.ApplicationDetailVO;
import com.bishe.job.vo.ApplicationItemVO;
import com.bishe.job.vo.ApplicationLogVO;
import com.bishe.job.vo.InterviewVO;
import com.bishe.job.vo.PositionTagVO;
import com.bishe.job.vo.ResumeVO;
import com.bishe.job.vo.SkillVO;
import com.bishe.job.vo.StatusOptionVO;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class RecruitmentServiceImpl implements RecruitmentService {

    private final JobApplicationMapper jobApplicationMapper;
    private final JobApplicationLogMapper jobApplicationLogMapper;
    private final JobInterviewMapper jobInterviewMapper;
    private final JobPositionMapper jobPositionMapper;
    private final EntCompanyMapper entCompanyMapper;
    private final SysUserMapper sysUserMapper;
    private final StuProfileMapper stuProfileMapper;
    private final StuResumeMapper stuResumeMapper;
    private final StuSkillMapper stuSkillMapper;
    private final SkillTagMapper skillTagMapper;
    private final VisibleJobSupport visibleJobSupport;
    private final CompanySupport companySupport;
    private final BehaviorLogService behaviorLogService;
    private final PositionTags positionTags;

    private static final int MATCH_SORT_LIMIT = 2000;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Long apply(ApplicationCreateDTO dto) {
        Long userId = UserContext.require().getId();
        JobPosition job = visibleJobSupport.require(dto.getJobId());
        if (PublicJobServiceImpl.EXT_ATS.equals(job.getDataSource())) {
            throw new BusinessException(400, "该职位来自外部招聘官网，请点击「前往官网投递」在企业官网投递");
        }
        StuResume resume = stuResumeMapper.selectById(dto.getResumeId());
        if (resume == null) {
            throw new BusinessException(404, "简历不存在");
        }
        if (!userId.equals(resume.getUserId())) {
            throw new BusinessException(403, "无权使用该简历");
        }
        JobApplication existing = jobApplicationMapper.selectAny(userId, job.getId());
        if (existing != null && Integer.valueOf(0).equals(existing.getDeleted())) {
            throw new BusinessException(400, "已投递");
        }
        LocalDateTime now = LocalDateTime.now();
        Long applicationId;
        if (existing != null) {
            jobApplicationMapper.revive(existing.getId(), resume.getId(), job.getCompanyId(), now);
            applicationId = existing.getId();
        } else {
            JobApplication created = new JobApplication();
            created.setUserId(userId);
            created.setPositionId(job.getId());
            created.setCompanyId(job.getCompanyId());
            created.setResumeId(resume.getId());
            created.setStatus(0);
            created.setApplyTime(now);
            created.setDeleted(0);
            jobApplicationMapper.insert(created);
            applicationId = created.getId();
        }
        insertLog(applicationId, null, 0, userId, "学生提交投递");
        jobPositionMapper.incrApply(job.getId());
        behaviorLogService.logJob(BehaviorLogService.APPLY, job.getId());
        return applicationId;
    }

    @Override
    public PageResult<ApplicationItemVO> studentPage(Integer status, long current, long size) {
        Long userId = UserContext.require().getId();
        Page<JobApplication> page = Pages.of(current, size);
        LambdaQueryWrapper<JobApplication> wrapper = new LambdaQueryWrapper<JobApplication>()
                .eq(JobApplication::getUserId, userId);
        if (status != null) {
            wrapper.eq(JobApplication::getStatus, status);
        }
        wrapper.orderByDesc(JobApplication::getUpdateTime).orderByDesc(JobApplication::getId);
        jobApplicationMapper.selectPage(page, wrapper);
        return PageResult.of(page, toItems(page.getRecords()));
    }

    @Override
    public ApplicationDetailVO studentDetail(Long id) {
        JobApplication application = requireApplication(id);
        if (!UserContext.require().getId().equals(application.getUserId())) {
            throw new BusinessException(403, "无权查看该投递");
        }
        return buildDetail(application);
    }

    @Override
    public List<InterviewVO> upcomingInterviews() {
        Long userId = UserContext.require().getId();
        LocalDateTime now = LocalDateTime.now();
        List<JobInterview> rows = jobInterviewMapper.selectList(new LambdaQueryWrapper<JobInterview>()
                .eq(JobInterview::getUserId, userId)
                .eq(JobInterview::getInterviewStatus, 0)
                .ge(JobInterview::getInterviewTime, now)
                .le(JobInterview::getInterviewTime, now.plusDays(7))
                .orderByAsc(JobInterview::getInterviewTime));
        return toInterviews(rows);
    }

    @Override
    public PageResult<ApplicationItemVO> companyPage(Long jobId, Integer status, String keyword, String sort,
                                                     long current, long size) {
        EntCompany company = companySupport.requireCurrent();
        Page<JobApplication> page = Pages.of(current, size);
        LambdaQueryWrapper<JobApplication> wrapper = new LambdaQueryWrapper<JobApplication>()
                .eq(JobApplication::getCompanyId, company.getId());
        if (jobId != null) {
            // 不能只按职位编号过滤：那会让其他企业用别人的 jobId 探测（虽然结果为空，仍应明确拒绝）
            JobPosition job = jobPositionMapper.selectById(jobId);
            if (job == null) {
                throw new BusinessException(404, "职位不存在");
            }
            if (!company.getId().equals(job.getCompanyId())) {
                throw new BusinessException(403, "无权查看该职位的投递");
            }
            wrapper.eq(JobApplication::getPositionId, jobId);
        }
        if (status != null) {
            wrapper.eq(JobApplication::getStatus, status);
        }
        if (!applyKeyword(wrapper, keyword, company.getId(), false)) {
            return PageResult.empty(page.getCurrent(), page.getSize());
        }
        wrapper.orderByDesc(JobApplication::getUpdateTime).orderByDesc(JobApplication::getId);
        if (sort != null && (sort.equals("matchDesc") || sort.equals("matchAsc"))) {
            // 匹配分不在库里，按匹配分排序时取出本企业筛选后的全部投递（上限 2000）在内存里算分、排序、分页
            List<ApplicationItemVO> all = toItems(jobApplicationMapper.selectList(wrapper.last("LIMIT " + MATCH_SORT_LIMIT)));
            fillSkillMatch(all);
            Comparator<Integer> byScore = sort.equals("matchDesc") ? Comparator.reverseOrder() : Comparator.naturalOrder();
            List<ApplicationItemVO> sorted = all.stream()
                    .sorted(Comparator.comparing(ApplicationItemVO::getMatchScore, Comparator.nullsLast(byScore)))
                    .toList();
            int from = (int) Math.min(sorted.size(), (page.getCurrent() - 1) * page.getSize());
            int to = (int) Math.min(sorted.size(), from + page.getSize());
            return new PageResult<>(sorted.subList(from, to), sorted.size(), page.getCurrent(), page.getSize());
        }
        if (sort != null && !sort.isBlank() && !sort.equals("updateTime")) {
            throw new BusinessException(400, "排序方式只支持 updateTime、matchDesc、matchAsc");
        }
        jobApplicationMapper.selectPage(page, wrapper);
        List<ApplicationItemVO> items = toItems(page.getRecords());
        fillSkillMatch(items);
        return PageResult.of(page, items);
    }

    /** 企业端列表与详情：候选人技能、熟练度、命中职位技能与匹配分。 */
    private void fillSkillMatch(List<? extends ApplicationItemVO> items) {
        if (items == null || items.isEmpty()) {
            return;
        }
        List<Long> userIds = items.stream().map(ApplicationItemVO::getUserId).distinct().toList();
        List<StuSkill> rows = stuSkillMapper.selectList(new LambdaQueryWrapper<StuSkill>()
                .in(StuSkill::getUserId, userIds)
                .orderByAsc(StuSkill::getId));
        Map<Long, String> tagNames = rows.isEmpty() ? Map.of() : skillTagMapper.selectBatchIds(
                        rows.stream().map(StuSkill::getTagId).distinct().toList())
                .stream().collect(Collectors.toMap(SkillTag::getId, SkillTag::getName, (a, b) -> a));
        Map<Long, Map<Long, Map.Entry<String, Integer>>> byUser = new HashMap<>();
        for (StuSkill row : rows) {
            String name = tagNames.get(row.getTagId());
            if (name != null) {
                byUser.computeIfAbsent(row.getUserId(), k -> new LinkedHashMap<>())
                        .putIfAbsent(row.getTagId(), Map.entry(name, row.getProficiency() == null ? 3 : row.getProficiency()));
            }
        }
        Map<Long, List<PositionTagVO>> jobTags = positionTags.of(items.stream().map(ApplicationItemVO::getJobId).toList());
        for (ApplicationItemVO item : items) {
            LinkedHashMap<Long, String> tags = new LinkedHashMap<>();
            for (PositionTagVO tag : jobTags.getOrDefault(item.getJobId(), List.of())) {
                tags.put(tag.getTagId(), tag.getTagName());
            }
            SkillMatch.Result match = SkillMatch.of(byUser.getOrDefault(item.getUserId(), Map.of()), tags);
            item.setCandidateSkills(match.skills());
            item.setMissingSkills(match.missing());
            item.setMatchedSkillCount(match.matched());
            item.setJobSkillCount(match.jobSkillCount());
            item.setMatchScore(match.score());
        }
    }

    @Override
    public ApplicationDetailVO companyDetail(Long id) {
        EntCompany company = companySupport.requireCurrent();
        JobApplication application = requireApplication(id);
        if (!company.getId().equals(application.getCompanyId())) {
            throw new BusinessException(403, "无权查看该投递");
        }
        ApplicationDetailVO detail = buildDetail(application);
        fillSkillMatch(List.of(detail));
        return detail;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void changeStatus(Long id, ApplicationStatusDTO dto) {
        EntCompany company = companySupport.requireCurrent();
        JobApplication application = requireApplication(id);
        if (!company.getId().equals(application.getCompanyId())) {
            throw new BusinessException(403, "无权操作该投递");
        }
        move(application, dto.getToStatus(), dto.getRemark(), UserContext.require().getId());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Long sendNotice(Long id, InterviewNoticeDTO dto) {
        EntCompany company = companySupport.requireCurrent();
        JobApplication application = requireApplication(id);
        if (!company.getId().equals(application.getCompanyId())) {
            throw new BusinessException(403, "无权操作该投递");
        }
        int status = application.getStatus() == null ? -1 : application.getStatus();
        if (status == 3 || status == 4) {
            throw new BusinessException(400, "当前投递已结束，不能发送笔试或面试通知");
        }
        if (Integer.valueOf(2).equals(dto.getInterviewType()) && !StringUtils.hasText(dto.getLocation())) {
            throw new BusinessException(400, "线下面试请填写地点");
        }
        if (Integer.valueOf(1).equals(dto.getInterviewType()) && !StringUtils.hasText(dto.getMeetingUrl())) {
            throw new BusinessException(400, "线上面试请填写会议链接");
        }
        String remark = trimToNull(dto.getRemark());
        Long operatorId = UserContext.require().getId();
        if (Integer.valueOf(1).equals(dto.getNoticeType()) && status == 0) {
            move(application, 1, remark == null ? "发送笔试通知" : remark, operatorId);
        } else if (Integer.valueOf(2).equals(dto.getNoticeType()) && (status == 0 || status == 1)) {
            move(application, 2, remark == null ? "发送面试通知" : remark, operatorId);
        }
        Integer maxRound = jobInterviewMapper.selectMaxRound(application.getId());
        JobInterview interview = new JobInterview();
        interview.setApplicationId(application.getId());
        interview.setUserId(application.getUserId());
        interview.setCompanyId(application.getCompanyId());
        interview.setPositionId(application.getPositionId());
        interview.setRoundNo(maxRound == null ? 1 : maxRound + 1);
        interview.setRoundName(StringUtils.hasText(dto.getRoundName())
                ? dto.getRoundName().trim()
                : (Integer.valueOf(1).equals(dto.getNoticeType()) ? "笔试" : "面试"));
        interview.setInterviewTime(dto.getInterviewTime());
        interview.setInterviewType(dto.getInterviewType());
        interview.setLocation(trimToNull(dto.getLocation()));
        interview.setMeetingUrl(trimToNull(dto.getMeetingUrl()));
        interview.setContactName(trimToNull(dto.getContactName()));
        interview.setContactPhone(trimToNull(dto.getContactPhone()));
        interview.setInterviewStatus(0);
        interview.setRemindAheadMinutes(1440);
        interview.setRemindStatus(0);
        interview.setRemark(remark);
        interview.setDeleted(0);
        jobInterviewMapper.insert(interview);
        return interview.getId();
    }

    @Override
    public PageResult<InterviewVO> companyInterviews(Integer interviewStatus, long current, long size) {
        EntCompany company = companySupport.requireCurrent();
        Page<JobInterview> page = Pages.of(current, size);
        LambdaQueryWrapper<JobInterview> wrapper = new LambdaQueryWrapper<JobInterview>()
                .eq(JobInterview::getCompanyId, company.getId());
        if (interviewStatus != null) {
            wrapper.eq(JobInterview::getInterviewStatus, interviewStatus);
        }
        wrapper.orderByDesc(JobInterview::getInterviewTime).orderByDesc(JobInterview::getId);
        jobInterviewMapper.selectPage(page, wrapper);
        return PageResult.of(page, toInterviews(page.getRecords()));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void saveInterviewResult(Long id, InterviewResultDTO dto) {
        EntCompany company = companySupport.requireCurrent();
        JobInterview interview = jobInterviewMapper.selectById(id);
        if (interview == null) {
            throw new BusinessException(404, "面试安排不存在");
        }
        if (!company.getId().equals(interview.getCompanyId())) {
            throw new BusinessException(403, "无权操作该面试");
        }
        interview.setInterviewStatus(dto.getInterviewStatus());
        if (dto.getRemark() != null) {
            interview.setRemark(dto.getRemark().trim());
        }
        jobInterviewMapper.updateById(interview);
    }

    @Override
    public PageResult<ApplicationItemVO> adminPage(Integer status, Long companyId, Long jobId, String keyword,
                                                    long current, long size) {
        Page<JobApplication> page = Pages.of(current, size);
        LambdaQueryWrapper<JobApplication> wrapper = new LambdaQueryWrapper<>();
        if (status != null) {
            wrapper.eq(JobApplication::getStatus, status);
        }
        if (companyId != null) {
            wrapper.eq(JobApplication::getCompanyId, companyId);
        }
        if (jobId != null) {
            wrapper.eq(JobApplication::getPositionId, jobId);
        }
        if (!applyKeyword(wrapper, keyword, null, true)) {
            return PageResult.empty(page.getCurrent(), page.getSize());
        }
        wrapper.orderByDesc(JobApplication::getUpdateTime).orderByDesc(JobApplication::getId);
        jobApplicationMapper.selectPage(page, wrapper);
        return PageResult.of(page, toItems(page.getRecords()));
    }

    @Override
    public AdminOverviewVO overview() {
        AdminOverviewVO vo = new AdminOverviewVO();
        vo.setJobTotal(nvl(jobPositionMapper.selectCount(null)));
        vo.setJobPending(nvl(jobPositionMapper.selectCount(new LambdaQueryWrapper<JobPosition>()
                .eq(JobPosition::getAuditStatus, 0))));
        vo.setJobOnline(nvl(jobPositionMapper.selectCount(new LambdaQueryWrapper<JobPosition>()
                .eq(JobPosition::getShelfStatus, 1))));
        vo.setApplicationTotal(nvl(jobApplicationMapper.selectCount(null)));
        vo.setCompanyTotal(nvl(entCompanyMapper.selectCount(null)));
        vo.setStudentTotal(nvl(sysUserMapper.selectCount(new LambdaQueryWrapper<SysUser>()
                .eq(SysUser::getRole, RoleCodes.STUDENT))));
        List<AdminOverviewVO.StatusCountVO> counts = new ArrayList<>();
        for (int status = 0; status <= 4; status++) {
            AdminOverviewVO.StatusCountVO item = new AdminOverviewVO.StatusCountVO();
            item.setStatus(status);
            item.setStatusName(ApplicationStateMachine.nameOf(status));
            item.setCount(nvl(jobApplicationMapper.selectCount(new LambdaQueryWrapper<JobApplication>()
                    .eq(JobApplication::getStatus, status))));
            counts.add(item);
        }
        vo.setApplicationStatusCounts(counts);
        return vo;
    }

    private void move(JobApplication application, int toStatus, String remark, Long operatorId) {
        int from = application.getStatus() == null ? -1 : application.getStatus();
        ApplicationStateMachine.assertCanTransit(from, toStatus);
        // 乐观并发控制：只有状态仍为 from 时才更新，防止并发操作导致越级迁移
        com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper<JobApplication> uw =
                new com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper<JobApplication>()
                        .eq(JobApplication::getId, application.getId())
                        .eq(JobApplication::getStatus, from)
                        .set(JobApplication::getStatus, toStatus);
        if (StringUtils.hasText(remark)) {
            uw.set(JobApplication::getRemark, remark.trim());
        }
        if (jobApplicationMapper.update(null, uw) != 1) {
            throw new BusinessException(409, "投递状态已被他人修改，请刷新后重试");
        }
        application.setStatus(toStatus);
        insertLog(application.getId(), from, toStatus, operatorId, remark);
    }

    private void insertLog(Long applicationId, Integer from, int to, Long operatorId, String remark) {
        JobApplicationLog row = new JobApplicationLog();
        row.setApplicationId(applicationId);
        row.setFromStatus(from);
        row.setToStatus(to);
        row.setOperatorId(operatorId);
        row.setRemark(trimToNull(remark));
        row.setDeleted(0);
        jobApplicationLogMapper.insert(row);
    }

    private JobApplication requireApplication(Long id) {
        JobApplication application = jobApplicationMapper.selectById(id);
        if (application == null) {
            throw new BusinessException(404, "投递记录不存在");
        }
        return application;
    }

    /**
     * @return false 表示关键词没有命中任何学生、职位或企业，调用方直接返回空页
     */
    private boolean applyKeyword(LambdaQueryWrapper<JobApplication> wrapper, String keyword,
                                 Long onlyCompanyId, boolean matchCompanyName) {
        if (!StringUtils.hasText(keyword)) {
            return true;
        }
        String kw = keyword.trim();
        List<Long> userIds = findStudentIds(kw);
        LambdaQueryWrapper<JobPosition> jobWrapper = new LambdaQueryWrapper<JobPosition>().like(JobPosition::getTitle, kw);
        if (onlyCompanyId != null) {
            jobWrapper.eq(JobPosition::getCompanyId, onlyCompanyId);
        }
        List<Long> jobIds = jobPositionMapper.selectList(jobWrapper).stream().map(JobPosition::getId).toList();
        List<Long> companyIds = List.of();
        if (matchCompanyName) {
            companyIds = entCompanyMapper.selectList(new LambdaQueryWrapper<EntCompany>()
                            .and(w -> w.like(EntCompany::getCompanyName, kw).or().like(EntCompany::getShortName, kw)))
                    .stream().map(EntCompany::getId).toList();
        }
        if (userIds.isEmpty() && jobIds.isEmpty() && companyIds.isEmpty()) {
            return false;
        }
        List<Long> users = userIds;
        List<Long> jobs = jobIds;
        List<Long> companies = companyIds;
        wrapper.and(w -> {
            boolean linked = false;
            if (!users.isEmpty()) {
                w.in(JobApplication::getUserId, users);
                linked = true;
            }
            if (!jobs.isEmpty()) {
                if (linked) {
                    w.or();
                }
                w.in(JobApplication::getPositionId, jobs);
                linked = true;
            }
            if (!companies.isEmpty()) {
                if (linked) {
                    w.or();
                }
                w.in(JobApplication::getCompanyId, companies);
            }
        });
        return true;
    }

    private List<Long> findStudentIds(String keyword) {
        Set<Long> ids = new LinkedHashSet<>();
        stuProfileMapper.selectList(new LambdaQueryWrapper<StuProfile>().like(StuProfile::getRealName, keyword))
                .forEach(profile -> ids.add(profile.getUserId()));
        sysUserMapper.selectList(new LambdaQueryWrapper<SysUser>()
                        .eq(SysUser::getRole, RoleCodes.STUDENT)
                        .like(SysUser::getNickname, keyword))
                .forEach(user -> ids.add(user.getId()));
        return new ArrayList<>(ids);
    }

    private List<ApplicationItemVO> toItems(List<JobApplication> applications) {
        if (applications == null || applications.isEmpty()) {
            return List.of();
        }
        Map<Long, JobPosition> jobs = mapJobs(applications.stream().map(JobApplication::getPositionId).toList());
        Map<Long, EntCompany> companies = mapCompanies(applications.stream().map(JobApplication::getCompanyId).toList());
        Map<Long, SysUser> users = mapUsers(applications.stream().map(JobApplication::getUserId).toList());
        Map<Long, StuProfile> profiles = mapProfiles(users.keySet());
        List<ApplicationItemVO> list = new ArrayList<>();
        for (JobApplication application : applications) {
            list.add(toItem(application, jobs, companies, users, profiles));
        }
        return list;
    }

    private ApplicationItemVO toItem(JobApplication application, Map<Long, JobPosition> jobs,
                                     Map<Long, EntCompany> companies, Map<Long, SysUser> users,
                                     Map<Long, StuProfile> profiles) {
        ApplicationItemVO vo = new ApplicationItemVO();
        vo.setId(application.getId());
        vo.setUserId(application.getUserId());
        vo.setJobId(application.getPositionId());
        vo.setCompanyId(application.getCompanyId());
        vo.setResumeId(application.getResumeId());
        vo.setStatus(application.getStatus());
        vo.setStatusName(ApplicationStateMachine.nameOf(application.getStatus()));
        vo.setRemark(application.getRemark());
        vo.setApplyTime(application.getApplyTime());
        vo.setUpdateTime(application.getUpdateTime());
        vo.setNextStatuses(ApplicationStateMachine.nextOf(application.getStatus()).stream()
                .map(status -> new StatusOptionVO(status, ApplicationStateMachine.nameOf(status)))
                .toList());
        JobPosition job = jobs.get(application.getPositionId());
        vo.setJobTitle(job == null ? "职位已删除" : job.getTitle());
        vo.setCity(job == null ? null : job.getCity());
        EntCompany company = companies.get(application.getCompanyId());
        if (company != null) {
            vo.setCompanyName(StringUtils.hasText(company.getShortName()) ? company.getShortName() : company.getCompanyName());
        }
        StuProfile profile = profiles.get(application.getUserId());
        SysUser user = users.get(application.getUserId());
        if (profile != null && StringUtils.hasText(profile.getRealName())) {
            vo.setStudentName(profile.getRealName());
        } else if (user != null) {
            vo.setStudentName(user.getNickname());
        }
        if (profile != null) {
            vo.setSchool(profile.getSchool());
            vo.setMajor(profile.getMajor());
            vo.setEducation(profile.getEducation());
            vo.setEducationName(educationName(profile.getEducation()));
        }
        return vo;
    }

    private ApplicationDetailVO buildDetail(JobApplication application) {
        ApplicationItemVO item = toItems(List.of(application)).get(0);
        ApplicationDetailVO detail = new ApplicationDetailVO();
        BeanUtils.copyProperties(item, detail);
        SysUser user = sysUserMapper.selectById(application.getUserId());
        if (user != null) {
            detail.setPhone(user.getPhone());
        }
        StuProfile profile = stuProfileMapper.selectOne(new LambdaQueryWrapper<StuProfile>()
                .eq(StuProfile::getUserId, application.getUserId()));
        if (profile != null) {
            detail.setGraduationYear(profile.getGraduationYear());
            detail.setExpectCity(profile.getExpectCity());
        }
        if (application.getResumeId() != null) {
            StuResume resume = stuResumeMapper.selectById(application.getResumeId());
            // 投递上的简历必须仍属于该学生，避免简历编号被改写后把别人的简历带出来
            if (resume != null && application.getUserId().equals(resume.getUserId())) {
                detail.setResume(toResume(resume));
            }
        }
        detail.setSkills(loadSkills(application.getUserId()));
        detail.setLogs(loadLogs(application.getId()));
        detail.setInterviews(toInterviews(jobInterviewMapper.selectList(new LambdaQueryWrapper<JobInterview>()
                .eq(JobInterview::getApplicationId, application.getId())
                .orderByAsc(JobInterview::getRoundNo)
                .orderByAsc(JobInterview::getId))));
        return detail;
    }

    private List<SkillVO> loadSkills(Long userId) {
        List<StuSkill> skills = stuSkillMapper.selectList(new LambdaQueryWrapper<StuSkill>()
                .eq(StuSkill::getUserId, userId)
                .orderByAsc(StuSkill::getId));
        if (skills.isEmpty()) {
            return List.of();
        }
        Map<Long, SkillTag> tags = skillTagMapper.selectBatchIds(skills.stream().map(StuSkill::getTagId).distinct().toList())
                .stream().collect(Collectors.toMap(SkillTag::getId, tag -> tag, (a, b) -> a));
        List<SkillVO> list = new ArrayList<>();
        for (StuSkill skill : skills) {
            SkillVO vo = new SkillVO();
            vo.setId(skill.getId());
            vo.setTagId(skill.getTagId());
            vo.setProficiency(skill.getProficiency());
            SkillTag tag = tags.get(skill.getTagId());
            if (tag != null) {
                vo.setTagName(tag.getName());
                vo.setDirection(tag.getDirection());
            }
            list.add(vo);
        }
        return list;
    }

    private List<ApplicationLogVO> loadLogs(Long applicationId) {
        List<JobApplicationLog> logs = jobApplicationLogMapper.selectList(new LambdaQueryWrapper<JobApplicationLog>()
                .eq(JobApplicationLog::getApplicationId, applicationId)
                .orderByAsc(JobApplicationLog::getId));
        Map<Long, SysUser> operators = mapUsers(logs.stream().map(JobApplicationLog::getOperatorId).toList());
        List<ApplicationLogVO> list = new ArrayList<>();
        for (JobApplicationLog log : logs) {
            ApplicationLogVO vo = new ApplicationLogVO();
            vo.setId(log.getId());
            vo.setApplicationId(log.getApplicationId());
            vo.setFromStatus(log.getFromStatus());
            vo.setFromStatusName(log.getFromStatus() == null ? "" : ApplicationStateMachine.nameOf(log.getFromStatus()));
            vo.setToStatus(log.getToStatus());
            vo.setToStatusName(ApplicationStateMachine.nameOf(log.getToStatus()));
            vo.setOperatorId(log.getOperatorId());
            SysUser operator = operators.get(log.getOperatorId());
            vo.setOperatorName(operator == null ? "" : (StringUtils.hasText(operator.getNickname()) ? operator.getNickname() : operator.getUsername()));
            vo.setRemark(log.getRemark());
            vo.setCreateTime(log.getCreateTime());
            list.add(vo);
        }
        return list;
    }

    private List<InterviewVO> toInterviews(List<JobInterview> rows) {
        if (rows == null || rows.isEmpty()) {
            return List.of();
        }
        Map<Long, JobPosition> jobs = mapJobs(rows.stream().map(JobInterview::getPositionId).toList());
        Map<Long, EntCompany> companies = mapCompanies(rows.stream().map(JobInterview::getCompanyId).toList());
        Map<Long, SysUser> users = mapUsers(rows.stream().map(JobInterview::getUserId).toList());
        Map<Long, StuProfile> profiles = mapProfiles(users.keySet());
        List<InterviewVO> list = new ArrayList<>();
        for (JobInterview row : rows) {
            InterviewVO vo = new InterviewVO();
            vo.setId(row.getId());
            vo.setApplicationId(row.getApplicationId());
            vo.setUserId(row.getUserId());
            vo.setCompanyId(row.getCompanyId());
            vo.setJobId(row.getPositionId());
            vo.setRoundNo(row.getRoundNo());
            vo.setRoundName(row.getRoundName());
            vo.setInterviewTime(row.getInterviewTime());
            vo.setInterviewType(row.getInterviewType());
            vo.setInterviewTypeName(Integer.valueOf(1).equals(row.getInterviewType()) ? "线上" : "线下");
            vo.setLocation(row.getLocation());
            vo.setMeetingUrl(row.getMeetingUrl());
            vo.setContactName(row.getContactName());
            vo.setContactPhone(row.getContactPhone());
            vo.setInterviewStatus(row.getInterviewStatus());
            vo.setInterviewStatusName(interviewStatusName(row.getInterviewStatus()));
            vo.setRemark(row.getRemark());
            JobPosition job = jobs.get(row.getPositionId());
            vo.setJobTitle(job == null ? "职位已删除" : job.getTitle());
            EntCompany company = companies.get(row.getCompanyId());
            if (company != null) {
                vo.setCompanyName(StringUtils.hasText(company.getShortName()) ? company.getShortName() : company.getCompanyName());
            }
            StuProfile profile = profiles.get(row.getUserId());
            SysUser user = users.get(row.getUserId());
            if (profile != null && StringUtils.hasText(profile.getRealName())) {
                vo.setStudentName(profile.getRealName());
            } else if (user != null) {
                vo.setStudentName(StringUtils.hasText(user.getNickname()) ? user.getNickname() : user.getUsername());
            }
            list.add(vo);
        }
        return list;
    }

    private ResumeVO toResume(StuResume resume) {
        ResumeVO vo = new ResumeVO();
        vo.setId(resume.getId());
        vo.setUserId(resume.getUserId());
        vo.setTitle(resume.getTitle());
        vo.setIsDefault(resume.getIsDefault());
        vo.setEducationExp(resume.getEducationExp());
        vo.setProjectExp(resume.getProjectExp());
        vo.setInternshipExp(resume.getInternshipExp());
        vo.setSkillDesc(resume.getSkillDesc());
        vo.setSelfEvaluation(resume.getSelfEvaluation());
        vo.setAttachmentUrl(resume.getAttachmentUrl());
        vo.setCreateTime(resume.getCreateTime());
        vo.setUpdateTime(resume.getUpdateTime());
        return vo;
    }

    private Map<Long, JobPosition> mapJobs(Collection<Long> ids) {
        List<Long> distinct = distinctIds(ids);
        if (distinct.isEmpty()) {
            return Map.of();
        }
        return jobPositionMapper.selectBatchIds(distinct).stream()
                .collect(Collectors.toMap(JobPosition::getId, job -> job, (a, b) -> a));
    }

    private Map<Long, EntCompany> mapCompanies(Collection<Long> ids) {
        List<Long> distinct = distinctIds(ids);
        if (distinct.isEmpty()) {
            return Map.of();
        }
        return entCompanyMapper.selectBatchIds(distinct).stream()
                .collect(Collectors.toMap(EntCompany::getId, company -> company, (a, b) -> a));
    }

    private Map<Long, SysUser> mapUsers(Collection<Long> ids) {
        List<Long> distinct = distinctIds(ids);
        if (distinct.isEmpty()) {
            return Map.of();
        }
        return sysUserMapper.selectBatchIds(distinct).stream()
                .collect(Collectors.toMap(SysUser::getId, user -> user, (a, b) -> a));
    }

    private Map<Long, StuProfile> mapProfiles(Collection<Long> userIds) {
        List<Long> distinct = distinctIds(userIds);
        if (distinct.isEmpty()) {
            return Map.of();
        }
        Map<Long, StuProfile> map = new HashMap<>();
        stuProfileMapper.selectList(new LambdaQueryWrapper<StuProfile>().in(StuProfile::getUserId, distinct))
                .forEach(profile -> map.put(profile.getUserId(), profile));
        return map;
    }

    private List<Long> distinctIds(Collection<Long> ids) {
        if (ids == null) {
            return List.of();
        }
        return ids.stream().filter(Objects::nonNull).distinct().toList();
    }

    private String educationName(Integer education) {
        if (education == null) {
            return "";
        }
        return switch (education) {
            case 1 -> "专科";
            case 2 -> "本科";
            case 3 -> "硕士";
            case 4 -> "博士";
            default -> "不限";
        };
    }

    private String interviewStatusName(Integer status) {
        if (status == null) {
            return "";
        }
        return switch (status) {
            case 0 -> "待进行";
            case 1 -> "已完成";
            case 2 -> "已取消";
            case 3 -> "学生缺席";
            default -> String.valueOf(status);
        };
    }

    private String trimToNull(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        return value.trim();
    }

    private long nvl(Long value) {
        return value == null ? 0L : value;
    }
}
