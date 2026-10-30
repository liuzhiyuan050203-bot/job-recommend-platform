package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.vo.ArticleVO;
import com.bishe.job.vo.BannerVO;
import com.bishe.job.vo.CategoryVO;
import com.bishe.job.vo.PostDetailVO;
import com.bishe.job.vo.PostVO;
import com.bishe.job.vo.SkillTagVO;

import java.util.List;

public interface PublicContentService {

    List<BannerVO> listBanners();

    PageResult<ArticleVO> listArticles(Integer type, String keyword, long current, long size);

    ArticleVO getArticle(Long id);

    List<CategoryVO> getCategoriesTree();

    List<SkillTagVO> listSkillTags(String direction);

    PageResult<PostVO> listPosts(Integer postType, Long companyId, String keyword, long current, long size);

    PostDetailVO getPost(Long id);
}
