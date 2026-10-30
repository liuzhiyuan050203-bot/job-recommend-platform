package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.dto.ArticleDTO;
import com.bishe.job.dto.ArticleStatusDTO;
import com.bishe.job.dto.BannerDTO;
import com.bishe.job.vo.ArticleVO;
import com.bishe.job.vo.BannerVO;

public interface AdminCmsService {

    // 轮播图
    PageResult<BannerVO> listBanners(long current, long size);

    void addBanner(BannerDTO dto);

    void updateBanner(Long id, BannerDTO dto);

    void deleteBanner(Long id);

    // 文章
    PageResult<ArticleVO> listArticles(Integer type, Integer status, String keyword, long current, long size);

    ArticleVO getArticle(Long id);

    void addArticle(ArticleDTO dto);

    void updateArticle(Long id, ArticleDTO dto);

    void updateArticleStatus(Long id, ArticleStatusDTO dto);

    void deleteArticle(Long id);
}
