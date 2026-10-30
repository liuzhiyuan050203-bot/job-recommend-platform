package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.dto.CommentCreateDTO;
import com.bishe.job.dto.PostCreateDTO;
import com.bishe.job.dto.PostUpdateDTO;
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
import com.bishe.job.service.StudentCommunityService;
import com.bishe.job.vo.PostVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class StudentCommunityServiceImpl implements StudentCommunityService {

    private final ComPostMapper comPostMapper;
    private final ComCommentMapper comCommentMapper;
    private final EntCompanyMapper entCompanyMapper;
    private final JobPositionMapper jobPositionMapper;
    private final SysUserMapper sysUserMapper;

    @Override
    public PageResult<PostVO> listMyPosts(long current, long size) {
        Long userId = UserContext.get().getId();
        Page<ComPost> page = Pages.of(current, size);
        LambdaQueryWrapper<ComPost> wrapper = new LambdaQueryWrapper<ComPost>()
                .eq(ComPost::getUserId, userId)
                .orderByDesc(ComPost::getCreateTime);

        comPostMapper.selectPage(page, wrapper);
        if (page.getRecords().isEmpty()) {
            return PageResult.of(page, Collections.emptyList());
        }

        List<PostVO> list = assemblePostVOs(page.getRecords());
        return PageResult.of(page, list);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void createPost(PostCreateDTO dto) {
        Long userId = UserContext.get().getId();

        ComPost post = new ComPost();
        post.setUserId(userId);
        post.setPostType(dto.getPostType());
        post.setTitle(dto.getTitle().trim());
        post.setContent(dto.getContent().trim());
        post.setRating(dto.getRating());
        post.setCompanyId(dto.getCompanyId());
        post.setPositionId(dto.getPositionId());
        post.setAuditStatus(0); // 待审核
        post.setAuditRemark("内容已提交，等待管理员审核");
        post.setLikeCount(0);

        comPostMapper.insert(post);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updatePost(Long id, PostUpdateDTO dto) {
        Long userId = UserContext.get().getId();
        ComPost post = comPostMapper.selectById(id);
        if (post == null || !post.getUserId().equals(userId)) {
            throw new BusinessException(404, "帖子不存在或无权修改");
        }

        post.setPostType(dto.getPostType());
        post.setTitle(dto.getTitle().trim());
        post.setContent(dto.getContent().trim());
        post.setRating(dto.getRating());
        post.setCompanyId(dto.getCompanyId());
        post.setPositionId(dto.getPositionId());
        // 修改后重新进入待审核
        post.setAuditStatus(0);
        post.setAuditRemark("修改后重新提交，等待审核");
        post.setAuditTime(null);
        post.setAuditorId(null);

        comPostMapper.updateById(post);
    }

    @Override
    public void deletePost(Long id) {
        Long userId = UserContext.get().getId();
        ComPost post = comPostMapper.selectById(id);
        if (post == null || !post.getUserId().equals(userId)) {
            throw new BusinessException(404, "帖子不存在或无权删除");
        }
        comPostMapper.deleteById(id);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void addComment(Long postId, CommentCreateDTO dto) {
        Long userId = UserContext.get().getId();
        ComPost post = comPostMapper.selectById(postId);
        // 只能评论已审核通过的帖子（自己的帖子除外）
        if (post == null || (!Integer.valueOf(1).equals(post.getAuditStatus()) && !userId.equals(post.getUserId()))) {
            throw new BusinessException(404, "评论目标帖子不存在或尚未通过审核");
        }

        ComComment comment = new ComComment();
        comment.setPostId(postId);
        comment.setUserId(userId);
        comment.setContent(dto.getContent().trim());
        comment.setAuditStatus(0); // 新评论待审核
        comment.setAuditRemark("评论已提交，等待管理员审核");

        comCommentMapper.insert(comment);
    }

    @Override
    public void deleteComment(Long commentId) {
        Long userId = UserContext.get().getId();
        ComComment comment = comCommentMapper.selectById(commentId);
        if (comment == null || !comment.getUserId().equals(userId)) {
            throw new BusinessException(404, "评论不存在或无权删除");
        }
        comCommentMapper.deleteById(commentId);
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
            vo.setPostTypeName(Integer.valueOf(1).equals(p.getPostType()) ? "面经分享" : "企业评价");
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
