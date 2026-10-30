package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.service.PublicContentService;
import com.bishe.job.vo.ArticleVO;
import com.bishe.job.vo.BannerVO;
import com.bishe.job.vo.CategoryVO;
import com.bishe.job.vo.PostDetailVO;
import com.bishe.job.vo.PostVO;
import com.bishe.job.vo.SkillTagVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/public")
@RequiredArgsConstructor
public class PublicContentController {

    private final PublicContentService publicContentService;

    @GetMapping("/banners")
    public Result<List<BannerVO>> listBanners() {
        return Result.success(publicContentService.listBanners());
    }

    @GetMapping("/articles")
    public Result<PageResult<ArticleVO>> listArticles(
            @RequestParam(value = "type", required = false) Integer type,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(publicContentService.listArticles(type, keyword, current, size));
    }

    @GetMapping("/articles/{id}")
    public Result<ArticleVO> getArticle(@PathVariable("id") Long id) {
        return Result.success(publicContentService.getArticle(id));
    }

    @GetMapping("/categories")
    public Result<List<CategoryVO>> getCategories() {
        return Result.success(publicContentService.getCategoriesTree());
    }

    @GetMapping("/skill-tags")
    public Result<List<SkillTagVO>> listSkillTags(
            @RequestParam(value = "direction", required = false) String direction) {
        return Result.success(publicContentService.listSkillTags(direction));
    }

    @GetMapping("/posts")
    public Result<PageResult<PostVO>> listPosts(
            @RequestParam(value = "postType", required = false) Integer postType,
            @RequestParam(value = "companyId", required = false) Long companyId,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(publicContentService.listPosts(postType, companyId, keyword, current, size));
    }

    @GetMapping("/posts/{id}")
    public Result<PostDetailVO> getPost(@PathVariable("id") Long id) {
        return Result.success(publicContentService.getPost(id));
    }
}
