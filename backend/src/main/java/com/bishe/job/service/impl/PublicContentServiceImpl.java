package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.entity.CmsArticle;
import com.bishe.job.entity.CmsBanner;
import com.bishe.job.entity.ComComment;
import com.bishe.job.entity.ComPost;
import com.bishe.job.entity.EntCompany;
import com.bishe.job.entity.JobCategory;
import com.bishe.job.entity.JobPosition;
import com.bishe.job.entity.SkillTag;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.CmsArticleMapper;
import com.bishe.job.mapper.CmsBannerMapper;
import com.bishe.job.mapper.ComCommentMapper;
import com.bishe.job.mapper.ComPostMapper;
import com.bishe.job.mapper.EntCompanyMapper;
import com.bishe.job.mapper.JobCategoryMapper;
import com.bishe.job.mapper.JobPositionMapper;
import com.bishe.job.mapper.SkillTagMapper;
import com.bishe.job.mapper.SysUserMapper;
import com.bishe.job.service.PublicContentService;
import com.bishe.job.vo.ArticleVO;
import com.bishe.job.vo.BannerVO;
import com.bishe.job.vo.CategoryVO;
import com.bishe.job.vo.CommentVO;
import com.bishe.job.vo.PostDetailVO;
import com.bishe.job.vo.PostVO;
import com.bishe.job.vo.SkillTagVO;
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
public class PublicContentServiceImpl implements PublicContentService {

    private final CmsBannerMapper cmsBannerMapper;
    private final CmsArticleMapper cmsArticleMapper;
    private final JobCategoryMapper jobCategoryMapper;
    private final SkillTagMapper skillTagMapper;
    private final ComPostMapper comPostMapper;
    private final ComCommentMapper comCommentMapper;
    private final SysUserMapper sysUserMapper;
    private final EntCompanyMapper entCompanyMapper;
    private final JobPositionMapper jobPositionMapper;

    @Override
    public List<BannerVO> listBanners() {
        LocalDateTime now = LocalDateTime.now();
        List<CmsBanner> banners = cmsBannerMapper.selectList(new LambdaQueryWrapper<CmsBanner>()
                .eq(CmsBanner::getStatus, 1)
                .and(w -> w.isNull(CmsBanner::getStartTime).or().le(CmsBanner::getStartTime, now))
                .and(w -> w.isNull(CmsBanner::getEndTime).or().ge(CmsBanner::getEndTime, now))
                .orderByAsc(CmsBanner::getSortNo)
                .orderByDesc(CmsBanner::getId));

        return banners.stream().map(this::toBannerVO).toList();
    }

    @Override
    public PageResult<ArticleVO> listArticles(Integer type, String keyword, long current, long size) {
        Page<CmsArticle> page = Pages.of(current, size);
        LambdaQueryWrapper<CmsArticle> wrapper = new LambdaQueryWrapper<CmsArticle>()
                .eq(CmsArticle::getStatus, 1);

        if (type != null) {
            wrapper.eq(CmsArticle::getArticleType, type);
        }
        if (StringUtils.hasText(keyword)) {
            String kw = keyword.trim();
            wrapper.and(w -> w.like(CmsArticle::getTitle, kw).or().like(CmsArticle::getSummary, kw));
        }

        wrapper.orderByDesc(CmsArticle::getTopFlag)
                .orderByDesc(CmsArticle::getPublishTime)
                .orderByDesc(CmsArticle::getId);

        cmsArticleMapper.selectPage(page, wrapper);

        if (page.getRecords().isEmpty()) {
            return PageResult.of(page, Collections.emptyList());
        }

        List<Long> publisherIds = page.getRecords().stream()
                .map(CmsArticle::getPublisherId)
                .distinct()
                .toList();
        Map<Long, String> publisherNames = sysUserMapper.selectBatchIds(publisherIds).stream()
                .collect(Collectors.toMap(SysUser::getId, u -> StringUtils.hasText(u.getNickname()) ? u.getNickname() : u.getUsername()));

        List<ArticleVO> list = page.getRecords().stream().map(a -> {
            ArticleVO vo = toArticleVO(a);
            vo.setPublisherName(publisherNames.get(a.getPublisherId()));
            return vo;
        }).toList();

        return PageResult.of(page, list);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ArticleVO getArticle(Long id) {
        CmsArticle article = cmsArticleMapper.selectById(id);
        if (article == null || article.getStatus() != 1) {
            throw new BusinessException(404, "文章不存在或未发布");
        }

        // 浏览数 + 1
        article.setViewCount(article.getViewCount() + 1);
        cmsArticleMapper.updateById(article);

        ArticleVO vo = toArticleVO(article);
        SysUser publisher = sysUserMapper.selectById(article.getPublisherId());
        if (publisher != null) {
            vo.setPublisherName(StringUtils.hasText(publisher.getNickname()) ? publisher.getNickname() : publisher.getUsername());
        }
        return vo;
    }

    @Override
    public List<CategoryVO> getCategoriesTree() {
        List<JobCategory> all = jobCategoryMapper.selectList(new LambdaQueryWrapper<JobCategory>()
                .eq(JobCategory::getStatus, 1)
                .orderByAsc(JobCategory::getSortNo)
                .orderByAsc(JobCategory::getId));

        Map<Long, CategoryVO> map = new HashMap<>();
        List<CategoryVO> roots = new ArrayList<>();

        for (JobCategory cat : all) {
            CategoryVO vo = new CategoryVO();
            vo.setId(cat.getId());
            vo.setParentId(cat.getParentId());
            vo.setName(cat.getName());
            vo.setSortNo(cat.getSortNo());
            vo.setStatus(cat.getStatus());
            map.put(cat.getId(), vo);
        }

        for (JobCategory cat : all) {
            CategoryVO vo = map.get(cat.getId());
            if (cat.getParentId() == null || !map.containsKey(cat.getParentId())) {
                roots.add(vo);
            } else {
                CategoryVO parent = map.get(cat.getParentId());
                parent.getChildren().add(vo);
            }
        }
        return roots;
    }

    @Override
    public List<SkillTagVO> listSkillTags(String direction) {
        LambdaQueryWrapper<SkillTag> wrapper = new LambdaQueryWrapper<SkillTag>()
                .eq(SkillTag::getStatus, 1);
        if (StringUtils.hasText(direction)) {
            wrapper.eq(SkillTag::getDirection, direction.trim());
        }
        wrapper.orderByAsc(SkillTag::getSortNo).orderByAsc(SkillTag::getId);

        return skillTagMapper.selectList(wrapper).stream().map(tag -> {
            SkillTagVO vo = new SkillTagVO();
            vo.setId(tag.getId());
            vo.setName(tag.getName());
            vo.setDirection(tag.getDirection());
            vo.setSortNo(tag.getSortNo());
            vo.setStatus(tag.getStatus());
            vo.setCreateTime(tag.getCreateTime());
            return vo;
        }).toList();
    }

    @Override
    public PageResult<PostVO> listPosts(Integer postType, Long companyId, String keyword, long current, long size) {
        Page<ComPost> page = Pages.of(current, size);
        LambdaQueryWrapper<ComPost> wrapper = new LambdaQueryWrapper<ComPost>()
                .eq(ComPost::getAuditStatus, 1);

        if (postType != null) {
            wrapper.eq(ComPost::getPostType, postType);
        }
        if (companyId != null) {
            wrapper.eq(ComPost::getCompanyId, companyId);
        }
        if (StringUtils.hasText(keyword)) {
            String kw = keyword.trim();
            wrapper.and(w -> w.like(ComPost::getTitle, kw).or().like(ComPost::getContent, kw));
        }
        wrapper.orderByDesc(ComPost::getCreateTime);

        comPostMapper.selectPage(page, wrapper);
        if (page.getRecords().isEmpty()) {
            return PageResult.of(page, Collections.emptyList());
        }

        List<PostVO> list = assemblePostVOs(page.getRecords());
        return PageResult.of(page, list);
    }

    @Override
    public PostDetailVO getPost(Long id) {
        ComPost post = comPostMapper.selectById(id);
        if (post == null || post.getAuditStatus() != 1) {
            throw new BusinessException(404, "帖子不存在或尚未通过审核");
        }

        List<PostVO> list = assemblePostVOs(List.of(post));
        PostVO baseVO = list.getFirst();

        PostDetailVO detailVO = new PostDetailVO();
        copyPostProperties(baseVO, detailVO);

        // 加载通过审核的评论
        List<ComComment> comments = comCommentMapper.selectList(new LambdaQueryWrapper<ComComment>()
                .eq(ComComment::getPostId, id)
                .eq(ComComment::getAuditStatus, 1)
                .orderByAsc(ComComment::getCreateTime));

        if (!comments.isEmpty()) {
            List<Long> userIds = comments.stream().map(ComComment::getUserId).distinct().toList();
            Map<Long, SysUser> userMap = sysUserMapper.selectBatchIds(userIds).stream()
                    .collect(Collectors.toMap(SysUser::getId, u -> u));

            List<CommentVO> commentVOList = comments.stream().map(c -> {
                CommentVO cvo = new CommentVO();
                cvo.setId(c.getId());
                cvo.setPostId(c.getPostId());
                cvo.setUserId(c.getUserId());
                cvo.setContent(c.getContent());
                cvo.setAuditStatus(c.getAuditStatus());
                cvo.setAuditRemark(c.getAuditRemark());
                cvo.setCreateTime(c.getCreateTime());
                SysUser user = userMap.get(c.getUserId());
                if (user != null) {
                    cvo.setAuthorName(StringUtils.hasText(user.getNickname()) ? user.getNickname() : user.getUsername());
                    cvo.setAuthorAvatar(user.getAvatar());
                }
                return cvo;
            }).toList();
            detailVO.setComments(commentVOList);
        }

        return detailVO;
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
        // 统计评论数
        Map<Long, Long> commentCountMap = new HashMap<>();
        for (Long pid : postIds) {
            Long count = comCommentMapper.selectCount(new LambdaQueryWrapper<ComComment>()
                    .eq(ComComment::getPostId, pid)
                    .eq(ComComment::getAuditStatus, 1));
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
            } else {
                vo.setAuthorName("匿名用户");
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

    private void copyPostProperties(PostVO source, PostDetailVO target) {
        target.setId(source.getId());
        target.setUserId(source.getUserId());
        target.setAuthorName(source.getAuthorName());
        target.setAuthorAvatar(source.getAuthorAvatar());
        target.setCompanyId(source.getCompanyId());
        target.setCompanyName(source.getCompanyName());
        target.setPositionId(source.getPositionId());
        target.setPositionTitle(source.getPositionTitle());
        target.setPostType(source.getPostType());
        target.setPostTypeName(source.getPostTypeName());
        target.setTitle(source.getTitle());
        target.setContent(source.getContent());
        target.setRating(source.getRating());
        target.setAuditStatus(source.getAuditStatus());
        target.setAuditRemark(source.getAuditRemark());
        target.setAuditTime(source.getAuditTime());
        target.setLikeCount(source.getLikeCount());
        target.setCommentCount(source.getCommentCount());
        target.setCreateTime(source.getCreateTime());
    }

    private BannerVO toBannerVO(CmsBanner banner) {
        BannerVO vo = new BannerVO();
        vo.setId(banner.getId());
        vo.setTitle(banner.getTitle());
        vo.setImageUrl(banner.getImageUrl());
        vo.setLinkUrl(banner.getLinkUrl());
        vo.setSortNo(banner.getSortNo());
        vo.setStatus(banner.getStatus());
        vo.setStartTime(banner.getStartTime());
        vo.setEndTime(banner.getEndTime());
        vo.setCreateTime(banner.getCreateTime());
        return vo;
    }

    private ArticleVO toArticleVO(CmsArticle article) {
        ArticleVO vo = new ArticleVO();
        vo.setId(article.getId());
        vo.setArticleType(article.getArticleType());
        vo.setArticleTypeName(articleTypeName(article.getArticleType()));
        vo.setTitle(article.getTitle());
        vo.setCoverUrl(article.getCoverUrl());
        vo.setSummary(article.getSummary());
        vo.setContent(article.getContent());
        vo.setPublisherId(article.getPublisherId());
        vo.setPublishTime(article.getPublishTime());
        vo.setTopFlag(article.getTopFlag());
        vo.setStatus(article.getStatus());
        vo.setViewCount(article.getViewCount());
        vo.setCreateTime(article.getCreateTime());
        return vo;
    }

    private String articleTypeName(Integer type) {
        if (type == null) return "其他";
        return switch (type) {
            case 1 -> "双选会公告";
            case 2 -> "就业政策";
            case 3 -> "新闻资讯";
            default -> "其他";
        };
    }
}
