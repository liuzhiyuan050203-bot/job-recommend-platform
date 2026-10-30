package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.dto.AuditDTO;
import com.bishe.job.entity.ComComment;
import com.bishe.job.entity.ComPost;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.JobPosition;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.ComCommentMapper;
import com.bishe.job.mapper.ComPostMapper;
import com.bishe.job.mapper.EntCompanyMapper;
import com.bishe.job.mapper.JobPositionMapper;
import com.bishe.job.mapper.SysUserMapper;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.AdminCommunityService;
import com.bishe.job.vo.CommentVO;
import com.bishe.job.vo.PostVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class AdminCommunityServiceImpl implements AdminCommunityService {

    private final ComPostMapper comPostMapper;
    private final ComCommentMapper comCommentMapper;
    private final SysUserMapper sysUserMapper;
    private final EntCompanyMapper entCompanyMapper;
    private final JobPositionMapper jobPositionMapper;

    @Override
    public PageResult<PostVO> listPosts(Integer auditStatus, String keyword, long current, long size) {
        Page<ComPost> page = Pages.of(current, size);
        LambdaQueryWrapper<ComPost> wrapper = new LambdaQueryWrapper<>();

        if (auditStatus != null) {
            wrapper.eq(ComPost::getAuditStatus, auditStatus);
        }
        if (StringUtils.hasText(keyword)) {
            String kw = keyword.trim();
            wrapper.and(w -> w.like(ComPost::getTitle, kw).or().like(ComPost::getContent, kw));
        }

        // 待审核 (0) 优先
        wrapper.orderByAsc(ComPost::getAuditStatus)
                .orderByDesc(ComPost::getUpdateTime)
                .orderByDesc(ComPost::getId);

        comPostMapper.selectPage(page, wrapper);
        if (page.getRecords().isEmpty()) {
            return PageResult.of(page, Collections.emptyList());
        }

        List<PostVO> list = assemblePostVOs(page.getRecords());
        return PageResult.of(page, list);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void auditPost(Long id, AuditDTO dto) {
        Long adminId = UserContext.get().getId();
        ComPost post = comPostMapper.selectById(id);
        if (post == null) {
            throw new BusinessException(404, "帖子不存在");
        }

        post.setAuditStatus(dto.getAuditStatus());
        post.setAuditRemark(dto.getAuditRemark());
        post.setAuditTime(LocalDateTime.now());
        post.setAuditorId(adminId);

        comPostMapper.updateById(post);
    }

    @Override
    public void deletePost(Long id) {
        ComPost post = comPostMapper.selectById(id);
        if (post == null) {
            throw new BusinessException(404, "帖子不存在");
        }
        comPostMapper.deleteById(id);
    }

    @Override
    public PageResult<CommentVO> listComments(Integer auditStatus, String keyword, long current, long size) {
        Page<ComComment> page = Pages.of(current, size);
        LambdaQueryWrapper<ComComment> wrapper = new LambdaQueryWrapper<>();

        if (auditStatus != null) {
            wrapper.eq(ComComment::getAuditStatus, auditStatus);
        }
        if (StringUtils.hasText(keyword)) {
            String kw = keyword.trim();
            wrapper.like(ComComment::getContent, kw);
        }

        wrapper.orderByAsc(ComComment::getAuditStatus)
                .orderByDesc(ComComment::getUpdateTime)
                .orderByDesc(ComComment::getId);

        comCommentMapper.selectPage(page, wrapper);
        if (page.getRecords().isEmpty()) {
            return PageResult.of(page, Collections.emptyList());
        }

        List<Long> userIds = page.getRecords().stream().map(ComComment::getUserId).distinct().toList();
        Map<Long, SysUser> userMap = sysUserMapper.selectBatchIds(userIds).stream()
                .collect(Collectors.toMap(SysUser::getId, u -> u));

        List<Long> postIds = page.getRecords().stream().map(ComComment::getPostId).distinct().toList();
        Map<Long, String> postTitleMap = comPostMapper.selectBatchIds(postIds).stream()
                .collect(Collectors.toMap(ComPost::getId, ComPost::getTitle));

        List<CommentVO> list = page.getRecords().stream().map(c -> {
            CommentVO vo = new CommentVO();
            vo.setId(c.getId());
            vo.setPostId(c.getPostId());
            vo.setPostTitle(postTitleMap.get(c.getPostId()));
            vo.setUserId(c.getUserId());
            SysUser u = userMap.get(c.getUserId());
            if (u != null) {
                vo.setAuthorName(StringUtils.hasText(u.getNickname()) ? u.getNickname() : u.getUsername());
                vo.setAuthorAvatar(u.getAvatar());
            }
            vo.setContent(c.getContent());
            vo.setAuditStatus(c.getAuditStatus());
            vo.setAuditRemark(c.getAuditRemark());
            vo.setAuditTime(c.getAuditTime());
            vo.setCreateTime(c.getCreateTime());
            return vo;
        }).toList();

        return PageResult.of(page, list);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void auditComment(Long id, AuditDTO dto) {
        Long adminId = UserContext.get().getId();
        ComComment comment = comCommentMapper.selectById(id);
        if (comment == null) {
            throw new BusinessException(404, "评论不存在");
        }

        comment.setAuditStatus(dto.getAuditStatus());
        comment.setAuditRemark(dto.getAuditRemark());
        comment.setAuditTime(LocalDateTime.now());
        comment.setAuditorId(adminId);

        comCommentMapper.updateById(comment);
    }

    @Override
    public void deleteComment(Long id) {
        ComComment comment = comCommentMapper.selectById(id);
        if (comment == null) {
            throw new BusinessException(404, "评论不存在");
        }
        comCommentMapper.deleteById(id);
    }

    private List<PostVO> assemblePostVOs(List<ComPost> posts) {
        List<Long> userIds = posts.stream().map(ComPost::getUserId).distinct().toList();
        Map<Long, SysUser> userMap = userIds.isEmpty() ? Collections.emptyMap() :
                sysUserMapper.selectBatchIds(userIds).stream().collect(Collectors.toMap(SysUser::getId, u -> u));

        List<Long> companyIds = posts.stream().map(ComPost::getCompanyId).filter(java.util.Objects::nonNull).distinct().toList();
        Map<Long, EntCompany> companyMap = companyIds.isEmpty() ? Collections.emptyMap() :
                entCompanyMapper.selectBatchIds(companyIds).stream().collect(Collectors.toMap(EntCompany::getId, c -> c));

        List<Long> positionIds = posts.stream().map(ComPost::getPositionId).filter(java.util.Objects::nonNull).distinct().toList();
        Map<Long, JobPosition> positionMap = positionIds.isEmpty() ? Collections.emptyMap() :
                jobPositionMapper.selectBatchIds(positionIds).stream().collect(Collectors.toMap(JobPosition::getId, p -> p));

        List<Long> postIds = posts.stream().map(ComPost::getId).toList();
        Map<Long, Long> commentCountMap = new HashMap<>();
        for (Long pid : postIds) {
            Long count = comCommentMapper.selectCount(new LambdaQueryWrapper<ComComment>()
                    .eq(ComComment::getPostId, pid));
            commentCountMap.put(pid, count);
        }

        List<PostVO> result = new ArrayList<>();
        for (ComPost p : posts) {
            PostVO vo = new PostVO();
            vo.setId(p.getId());
            vo.setUserId(p.getUserId());
            SysUser author = userMap.get(p.getUserId());
            if (author != null) {
                vo.setAuthorName(StringUtils.hasText(author.getNickname()) ? author.getNickname() : author.getUsername());
                vo.setAuthorAvatar(author.getAvatar());
            }

            vo.setCompanyId(p.getCompanyId());
            if (p.getCompanyId() != null) {
                EntCompany company = companyMap.get(p.getCompanyId());
                if (company != null) {
                    vo.setCompanyName(StringUtils.hasText(company.getShortName()) ? company.getShortName() : company.getCompanyName());
                }
            }

            vo.setPositionId(p.getPositionId());
            if (p.getPositionId() != null) {
                JobPosition pos = positionMap.get(p.getPositionId());
                if (pos != null) {
                    vo.setPositionTitle(pos.getTitle());
                }
            }

            vo.setPostType(p.getPostType());
            vo.setPostTypeName(p.getPostType() == 1 ? "面经分享" : "企业评价");
            vo.setTitle(p.getTitle());
            vo.setContent(p.getContent());
            vo.setRating(p.getRating());
            vo.setAuditStatus(p.getAuditStatus());
            vo.setAuditRemark(p.getAuditRemark());
            vo.setAuditTime(p.getAuditTime());
            vo.setLikeCount(p.getLikeCount());
            vo.setCommentCount(commentCountMap.getOrDefault(p.getId(), 0L).intValue());
            vo.setCreateTime(p.getCreateTime());

            result.add(vo);
        }
        return result;
    }
}
