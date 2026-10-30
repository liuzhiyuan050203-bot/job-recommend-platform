package com.bishe.job.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bishe.job.common.BusinessException;
import com.bishe.job.common.PageResult;
import com.bishe.job.common.Pages;
import com.bishe.job.dto.ArticleDTO;
import com.bishe.job.dto.ArticleStatusDTO;
import com.bishe.job.dto.BannerDTO;
import com.bishe.job.entity.CmsArticle;
import com.bishe.job.entity.CmsBanner;
import com.bishe.job.entity.SysUser;
import com.bishe.job.mapper.CmsArticleMapper;
import com.bishe.job.mapper.CmsBannerMapper;
import com.bishe.job.mapper.SysUserMapper;
import com.bishe.job.security.UserContext;
import com.bishe.job.service.AdminCmsService;
import com.bishe.job.vo.ArticleVO;
import com.bishe.job.vo.BannerVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class AdminCmsServiceImpl implements AdminCmsService {

    private final CmsBannerMapper cmsBannerMapper;
    private final CmsArticleMapper cmsArticleMapper;
    private final SysUserMapper sysUserMapper;

    @Override
    public PageResult<BannerVO> listBanners(long current, long size) {
        Page<CmsBanner> page = Pages.of(current, size);
        LambdaQueryWrapper<CmsBanner> wrapper = new LambdaQueryWrapper<CmsBanner>()
                .orderByAsc(CmsBanner::getSortNo)
                .orderByDesc(CmsBanner::getId);

        cmsBannerMapper.selectPage(page, wrapper);
        if (page.getRecords().isEmpty()) {
            return PageResult.of(page, Collections.emptyList());
        }

        List<BannerVO> list = page.getRecords().stream().map(this::toBannerVO).toList();
        return PageResult.of(page, list);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void addBanner(BannerDTO dto) {
        CmsBanner banner = new CmsBanner();
        banner.setTitle(dto.getTitle().trim());
        banner.setImageUrl(dto.getImageUrl().trim());
        banner.setLinkUrl(dto.getLinkUrl());
        banner.setSortNo(dto.getSortNo() != null ? dto.getSortNo() : 0);
        banner.setStatus(dto.getStatus() != null ? dto.getStatus() : 1);
        banner.setStartTime(dto.getStartTime());
        banner.setEndTime(dto.getEndTime());

        cmsBannerMapper.insert(banner);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateBanner(Long id, BannerDTO dto) {
        CmsBanner banner = cmsBannerMapper.selectById(id);
        if (banner == null) {
            throw new BusinessException(404, "轮播图不存在");
        }

        banner.setTitle(dto.getTitle().trim());
        banner.setImageUrl(dto.getImageUrl().trim());
        banner.setLinkUrl(dto.getLinkUrl());
        if (dto.getSortNo() != null) {
            banner.setSortNo(dto.getSortNo());
        }
        if (dto.getStatus() != null) {
            banner.setStatus(dto.getStatus());
        }
        banner.setStartTime(dto.getStartTime());
        banner.setEndTime(dto.getEndTime());

        cmsBannerMapper.updateById(banner);
    }

    @Override
    public void deleteBanner(Long id) {
        CmsBanner banner = cmsBannerMapper.selectById(id);
        if (banner == null) {
            throw new BusinessException(404, "轮播图不存在");
        }
        cmsBannerMapper.deleteById(id);
    }

    @Override
    public PageResult<ArticleVO> listArticles(Integer type, Integer status, String keyword, long current, long size) {
        Page<CmsArticle> page = Pages.of(current, size);
        LambdaQueryWrapper<CmsArticle> wrapper = new LambdaQueryWrapper<>();

        if (type != null) {
            wrapper.eq(CmsArticle::getArticleType, type);
        }
        if (status != null) {
            wrapper.eq(CmsArticle::getStatus, status);
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

        List<Long> publisherIds = page.getRecords().stream().map(CmsArticle::getPublisherId).distinct().toList();
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
    public ArticleVO getArticle(Long id) {
        CmsArticle article = cmsArticleMapper.selectById(id);
        if (article == null) {
            throw new BusinessException(404, "文章不存在");
        }
        ArticleVO vo = toArticleVO(article);
        SysUser publisher = sysUserMapper.selectById(article.getPublisherId());
        if (publisher != null) {
            vo.setPublisherName(StringUtils.hasText(publisher.getNickname()) ? publisher.getNickname() : publisher.getUsername());
        }
        return vo;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void addArticle(ArticleDTO dto) {
        Long adminId = UserContext.get().getId();

        CmsArticle article = new CmsArticle();
        article.setArticleType(dto.getArticleType());
        article.setTitle(dto.getTitle().trim());
        article.setCoverUrl(dto.getCoverUrl());
        article.setSummary(dto.getSummary());
        article.setContent(dto.getContent().trim());
        article.setPublisherId(adminId);
        article.setTopFlag(dto.getTopFlag() != null ? dto.getTopFlag() : 0);
        int status = dto.getStatus() != null ? dto.getStatus() : 0;
        article.setStatus(status);
        if (status == 1) {
            article.setPublishTime(LocalDateTime.now());
        }
        article.setViewCount(0);

        cmsArticleMapper.insert(article);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateArticle(Long id, ArticleDTO dto) {
        CmsArticle article = cmsArticleMapper.selectById(id);
        if (article == null) {
            throw new BusinessException(404, "文章不存在");
        }

        article.setArticleType(dto.getArticleType());
        article.setTitle(dto.getTitle().trim());
        article.setCoverUrl(dto.getCoverUrl());
        article.setSummary(dto.getSummary());
        article.setContent(dto.getContent().trim());
        if (dto.getTopFlag() != null) {
            article.setTopFlag(dto.getTopFlag());
        }
        if (dto.getStatus() != null) {
            int newStatus = dto.getStatus();
            if (newStatus == 1 && (article.getStatus() != 1 || article.getPublishTime() == null)) {
                article.setPublishTime(LocalDateTime.now());
            }
            article.setStatus(newStatus);
        }

        cmsArticleMapper.updateById(article);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateArticleStatus(Long id, ArticleStatusDTO dto) {
        CmsArticle article = cmsArticleMapper.selectById(id);
        if (article == null) {
            throw new BusinessException(404, "文章不存在");
        }

        int newStatus = dto.getStatus();
        article.setStatus(newStatus);
        if (newStatus == 1 && article.getPublishTime() == null) {
            article.setPublishTime(LocalDateTime.now());
        }

        cmsArticleMapper.updateById(article);
    }

    @Override
    public void deleteArticle(Long id) {
        CmsArticle article = cmsArticleMapper.selectById(id);
        if (article == null) {
            throw new BusinessException(404, "文章不存在");
        }
        cmsArticleMapper.deleteById(id);
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
