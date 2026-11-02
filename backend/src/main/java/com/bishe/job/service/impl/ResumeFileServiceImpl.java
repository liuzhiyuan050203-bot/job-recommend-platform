package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bishe.job.client.FastApiClient;
import com.bishe.job.common.BusinessException;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.JobApplication;
import com.bishe.job.entity.SkillTag;
import com.bishe.job.entity.StuProfile;
import com.bishe.job.entity.StuResume;
import com.bishe.job.entity.StuSkill;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.JobApplicationMapper;
import com.bishe.job.mapper.SkillTagMapper;
import com.bishe.job.mapper.StuProfileMapper;
import com.bishe.job.mapper.StuResumeMapper;
import com.bishe.job.mapper.StuSkillMapper;
import com.bishe.job.mapper.SysUserMapper;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.CompanySupport;
import com.bishe.job.service.ResumeDownload;
import com.bishe.job.service.ResumeFileService;
import com.bishe.job.service.ResumeSkillSync;
import com.bishe.job.vo.ResumeParseVO;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * 简历原件只落在本机目录，下载必须先核对学生本人或录用该简历的企业。
 */
@Slf4j
@Service
public class ResumeFileServiceImpl implements ResumeFileService {

    static final long MAX_BYTES = 5L * 1024 * 1024;
    private static final int NEW_SKILL_LEVEL = 3;
    private static final byte[] DOCX_MARKER = "word/document.xml".getBytes(StandardCharsets.US_ASCII);

    private final StuResumeMapper stuResumeMapper;
    private final StuSkillMapper stuSkillMapper;
    private final SkillTagMapper skillTagMapper;
    private final StuProfileMapper stuProfileMapper;
    private final SysUserMapper sysUserMapper;
    private final JobApplicationMapper jobApplicationMapper;
    private final CompanySupport companySupport;
    private final FastApiClient fastApiClient;
    private final Path uploadRoot;

    public ResumeFileServiceImpl(StuResumeMapper stuResumeMapper,
                                 StuSkillMapper stuSkillMapper,
                                 SkillTagMapper skillTagMapper,
                                 StuProfileMapper stuProfileMapper,
                                 SysUserMapper sysUserMapper,
                                 JobApplicationMapper jobApplicationMapper,
                                 CompanySupport companySupport,
                                 FastApiClient fastApiClient,
                                 @Value("${resume.upload-dir}") String uploadDir) {
        this.stuResumeMapper = stuResumeMapper;
        this.stuSkillMapper = stuSkillMapper;
        this.skillTagMapper = skillTagMapper;
        this.stuProfileMapper = stuProfileMapper;
        this.sysUserMapper = sysUserMapper;
        this.jobApplicationMapper = jobApplicationMapper;
        this.companySupport = companySupport;
        this.fastApiClient = fastApiClient;
        Path configured = Path.of(uploadDir);
        if (!configured.isAbsolute()) {
            configured = Path.of(System.getProperty("user.dir")).resolve(configured);
        }
        this.uploadRoot = configured.toAbsolutePath().normalize();
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ResumeParseVO upload(MultipartFile file) {
        Long userId = UserContext.require().getId();
        if (file == null || file.isEmpty()) {
            throw new BusinessException(400, "文件为空");
        }
        String ext = extensionOf(file.getOriginalFilename());
        if (ext.isEmpty()) {
            throw new BusinessException(400, "只支持 PDF 或 DOCX");
        }
        if (file.getSize() > MAX_BYTES) {
            throw new BusinessException(400, "文件不能超过 5MB");
        }
        byte[] bytes;
        try {
            bytes = file.getBytes();
        } catch (IOException ex) {
            throw new BusinessException(400, "读取上传文件失败");
        }
        if (bytes.length > MAX_BYTES) {
            throw new BusinessException(400, "文件不能超过 5MB");
        }
        assertMagic(ext, bytes);

        String storedName = UUID.randomUUID() + "." + ext;
        String key = userId + "/" + storedName;
        Path target = resolveKey(key);
        try {
            Files.createDirectories(target.getParent());
            Files.write(target, bytes);
        } catch (IOException ex) {
            log.warn("保存简历原件失败 userId={}", userId);
            throw new BusinessException(500, "保存简历文件失败");
        }

        JsonNode parsed;
        try {
            parsed = fastApiClient.parseResume(storedName, bytes);
        } catch (RuntimeException ex) {
            deleteQuietly(target);
            throw ex;
        }

        StuResume resume = ensureResume(userId);
        String previous = resume.getAttachmentUrl();
        resume.setAttachmentUrl(key);
        stuResumeMapper.updateById(resume);
        deletePrevious(userId, previous, key);

        ResumeParseVO vo = new ResumeParseVO();
        vo.setTextPreview(parsed.path("textPreview").asText(""));
        vo.setResumeId(resume.getId());
        vo.setSkills(readSkills(parsed.path("skills")));
        return vo;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void mergeSkills(List<Long> tagIds) {
        Long userId = UserContext.require().getId();
        if (tagIds == null || tagIds.isEmpty()) {
            throw new BusinessException(400, "请选择要合并的技能");
        }
        Set<Long> unique = new LinkedHashSet<>();
        for (Long tagId : tagIds) {
            if (tagId != null) {
                unique.add(tagId);
            }
        }
        if (unique.isEmpty()) {
            throw new BusinessException(400, "请选择要合并的技能");
        }
        for (Long tagId : unique) {
            SkillTag tag = skillTagMapper.selectById(tagId);
            if (tag == null || tag.getStatus() == null || tag.getStatus() != 1) {
                throw new BusinessException(400, "技能标签不存在或已停用");
            }
            StuSkill existing = stuSkillMapper.selectWithDeleted(userId, tagId);
            if (existing == null) {
                StuSkill created = new StuSkill();
                created.setUserId(userId);
                created.setTagId(tagId);
                created.setProficiency(NEW_SKILL_LEVEL);
                created.setDeleted(0);
                stuSkillMapper.insert(created);
                continue;
            }
            // 已有记录保留熟练度；逻辑删除的按原熟练度恢复，避免覆盖学生自己打的星
            if (existing.getDeleted() != null && existing.getDeleted() == 1) {
                int level = existing.getProficiency() == null ? NEW_SKILL_LEVEL : existing.getProficiency();
                stuSkillMapper.restoreSkill(existing.getId(), level);
            }
        }
        // 同步到默认在线简历 skillDesc，投递时企业端看到的技能来自档案，简历正文也要一致
        List<String> names = skillTagMapper.selectBatchIds(new ArrayList<>(unique)).stream()
                .map(SkillTag::getName)
                .filter(Objects::nonNull)
                .collect(Collectors.toList());
        syncSkillsToDefaultResume(userId, names);
    }

    @Override
    public void refreshRecommend() {
        Long userId = UserContext.require().getId();
        try {
            fastApiClient.recommendUser(userId, 10);
        } catch (RuntimeException ex) {
            log.warn("合并技能后刷新实时推荐失败 userId={}: {}", userId, ex.getMessage());
        }
    }

    @Override
    public ResumeDownload downloadOwn(Long resumeId) {
        StuResume resume = requireOwn(resumeId);
        return readStored(resume);
    }

    @Override
    public ResumeDownload downloadForCompany(Long applicationId) {
        EntCompany company = companySupport.requireCurrent();
        JobApplication application = jobApplicationMapper.selectById(applicationId);
        if (application == null) {
            throw new BusinessException(404, "投递记录不存在");
        }
        if (!company.getId().equals(application.getCompanyId())) {
            throw new BusinessException(403, "无权查看该投递");
        }
        if (application.getResumeId() == null) {
            throw new BusinessException(404, "简历附件不存在");
        }
        StuResume resume = stuResumeMapper.selectById(application.getResumeId());
        if (resume == null || !application.getUserId().equals(resume.getUserId())) {
            throw new BusinessException(404, "简历附件不存在");
        }
        return readStored(resume);
    }

    private StuResume requireOwn(Long resumeId) {
        StuResume resume = stuResumeMapper.selectById(resumeId);
        if (resume == null) {
            throw new BusinessException(404, "简历不存在");
        }
        if (!UserContext.require().getId().equals(resume.getUserId())) {
            throw new BusinessException(403, "无权操作该简历");
        }
        return resume;
    }

    private ResumeDownload readStored(StuResume resume) {
        String key = resume.getAttachmentUrl();
        if (!StringUtils.hasText(key) || !key.matches(resume.getUserId() + "/[0-9a-fA-F\\-]{36}\\.(pdf|docx)")) {
            throw new BusinessException(404, "简历附件不存在");
        }
        Path file = resolveKey(key.trim());
        if (!Files.isRegularFile(file)) {
            throw new BusinessException(404, "简历附件不存在");
        }
        try {
            byte[] bytes = Files.readAllBytes(file);
            boolean pdf = key.endsWith(".pdf");
            String filename = pdf ? "resume.pdf" : "resume.docx";
            String type = pdf ? "application/pdf"
                    : "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
            return new ResumeDownload(bytes, filename, type);
        } catch (IOException ex) {
            throw new BusinessException(404, "简历附件不存在");
        }
    }

    /**
     * 只接受落在上传根目录内的相对路径，拒绝 .. 和绝对路径。
     */
    private Path resolveKey(String key) {
        String normalized = key.replace('\\', '/');
        if (normalized.contains("..") || normalized.startsWith("/") || normalized.contains(":")) {
            throw new BusinessException(404, "简历附件不存在");
        }
        Path file = uploadRoot.resolve(normalized).normalize();
        if (!file.startsWith(uploadRoot)) {
            throw new BusinessException(404, "简历附件不存在");
        }
        return file;
    }

    /**
     * 选取或创建一份可投递的默认在线简历：优先非测试标题的默认简历，再任意非测试简历，
     * 否则新建「姓名-校招简历」。测试/污染标题不会被当作默认同步目标。
     */
    private StuResume ensureResume(Long userId) {
        List<StuResume> all = stuResumeMapper.selectList(new LambdaQueryWrapper<StuResume>()
                .eq(StuResume::getUserId, userId)
                .orderByDesc(StuResume::getIsDefault)
                .orderByDesc(StuResume::getUpdateTime)
                .orderByDesc(StuResume::getId));
        List<StuResume> usable = all.stream()
                .filter(r -> !ResumeSkillSync.isTestTitle(r.getTitle()))
                .toList();
        if (!usable.isEmpty()) {
            StuResume pick = usable.get(0);
            if (!Integer.valueOf(1).equals(pick.getIsDefault())) {
                for (StuResume row : all) {
                    if (Integer.valueOf(1).equals(row.getIsDefault())) {
                        row.setIsDefault(0);
                        stuResumeMapper.updateById(row);
                    }
                }
                pick.setIsDefault(1);
                stuResumeMapper.updateById(pick);
            }
            return pick;
        }
        return createCampusResume(userId);
    }

    private StuResume createCampusResume(Long userId) {
        StuProfile profile = stuProfileMapper.selectOne(new LambdaQueryWrapper<StuProfile>()
                .eq(StuProfile::getUserId, userId)
                .last("LIMIT 1"));
        SysUser user = sysUserMapper.selectById(userId);
        String realName = profile == null ? null : profile.getRealName();
        String nickname = user == null ? null : user.getNickname();
        StuResume created = new StuResume();
        created.setUserId(userId);
        created.setTitle(ResumeSkillSync.campusResumeTitle(realName, nickname));
        created.setIsDefault(1);
        created.setEducationExp("");
        created.setProjectExp("");
        created.setInternshipExp("");
        created.setSkillDesc("");
        created.setSelfEvaluation("");
        created.setAttachmentUrl("");
        created.setDeleted(0);
        stuResumeMapper.insert(created);
        return created;
    }

    /** 把合并进档案的技能名写入默认在线简历 skillDesc（没有则创建校招简历）。 */
    private void syncSkillsToDefaultResume(Long userId, List<String> skillNames) {
        if (skillNames == null || skillNames.isEmpty()) {
            return;
        }
        StuResume resume = ensureResume(userId);
        String merged = ResumeSkillSync.mergeSkillDesc(resume.getSkillDesc(), skillNames);
        if (!Objects.equals(merged, resume.getSkillDesc())) {
            resume.setSkillDesc(merged);
            stuResumeMapper.updateById(resume);
        }
    }

    private void deletePrevious(Long userId, String previous, String current) {
        if (!StringUtils.hasText(previous) || previous.equals(current)) {
            return;
        }
        if (!previous.matches(userId + "/[0-9a-fA-F\\-]{36}\\.(pdf|docx)")) {
            return;
        }
        try {
            Files.deleteIfExists(resolveKey(previous));
        } catch (IOException | BusinessException ex) {
            log.info("旧简历原件未删除");
        }
    }

    private void deleteQuietly(Path target) {
        try {
            Files.deleteIfExists(target);
        } catch (IOException ex) {
            log.info("解析失败后的临时简历未删除");
        }
    }

    private List<ResumeParseVO.MatchedSkillVO> readSkills(JsonNode node) {
        List<ResumeParseVO.MatchedSkillVO> list = new ArrayList<>();
        if (node == null || !node.isArray()) {
            return list;
        }
        for (JsonNode item : node) {
            long tagId = item.path("tagId").asLong(0);
            if (tagId <= 0) {
                continue;
            }
            ResumeParseVO.MatchedSkillVO skill = new ResumeParseVO.MatchedSkillVO();
            skill.setTagId(tagId);
            skill.setName(item.path("name").asText(""));
            skill.setDirection(item.path("direction").asText(""));
            skill.setEvidence(item.path("evidence").asText(""));
            list.add(skill);
        }
        return list;
    }

    private String extensionOf(String original) {
        if (!StringUtils.hasText(original)) {
            return "";
        }
        String name = Path.of(original).getFileName().toString().toLowerCase(Locale.ROOT);
        if (name.endsWith(".pdf")) {
            return "pdf";
        }
        if (name.endsWith(".docx")) {
            return "docx";
        }
        return "";
    }

    private void assertMagic(String ext, byte[] data) {
        if ("pdf".equals(ext)) {
            if (data.length < 5 || data[0] != '%' || data[1] != 'P' || data[2] != 'D' || data[3] != 'F') {
                throw new BusinessException(400, "文件内容与扩展名不符");
            }
            return;
        }
        if (data.length < 4 || data[0] != 'P' || data[1] != 'K') {
            throw new BusinessException(400, "文件内容与扩展名不符");
        }
        if (!contains(data, DOCX_MARKER)) {
            throw new BusinessException(400, "文件内容与扩展名不符");
        }
    }

    private boolean contains(byte[] data, byte[] needle) {
        if (needle.length == 0 || data.length < needle.length) {
            return false;
        }
        outer:
        for (int i = 0; i <= data.length - needle.length; i++) {
            for (int j = 0; j < needle.length; j++) {
                if (data[i + j] != needle[j]) {
                    continue outer;
                }
            }
            return true;
        }
        return false;
    }
}
