package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.ArticleDTO;
import com.bishe.job.dto.ArticleStatusDTO;
import com.bishe.job.dto.BannerDTO;
import com.bishe.job.service.AdminCmsService;
import com.bishe.job.vo.ArticleVO;
import com.bishe.job.vo.BannerVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
public class AdminCmsController {

    private final AdminCmsService adminCmsService;

    // --- 轮播图管理 ---

    @GetMapping("/banners")
    public Result<PageResult<BannerVO>> listBanners(
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(adminCmsService.listBanners(current, size));
    }

    @PostMapping("/banners")
    public Result<Void> addBanner(@Valid @RequestBody BannerDTO dto) {
        adminCmsService.addBanner(dto);
        return Result.success("轮播图添加成功", null);
    }

    @PutMapping("/banners/{id}")
    public Result<Void> updateBanner(@PathVariable("id") Long id,
                                     @Valid @RequestBody BannerDTO dto) {
        adminCmsService.updateBanner(id, dto);
        return Result.success("轮播图更新成功", null);
    }

    @DeleteMapping("/banners/{id}")
    public Result<Void> deleteBanner(@PathVariable("id") Long id) {
        adminCmsService.deleteBanner(id);
        return Result.success("轮播图删除成功", null);
    }

    // --- 文章资讯管理 ---

    @GetMapping("/articles")
    public Result<PageResult<ArticleVO>> listArticles(
            @RequestParam(value = "type", required = false) Integer type,
            @RequestParam(value = "status", required = false) Integer status,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(adminCmsService.listArticles(type, status, keyword, current, size));
    }

    @GetMapping("/articles/{id}")
    public Result<ArticleVO> getArticle(@PathVariable("id") Long id) {
        return Result.success(adminCmsService.getArticle(id));
    }

    @PostMapping("/articles")
    public Result<Void> addArticle(@Valid @RequestBody ArticleDTO dto) {
        adminCmsService.addArticle(dto);
        return Result.success("文章发布/保存成功", null);
    }

    @PutMapping("/articles/{id}")
    public Result<Void> updateArticle(@PathVariable("id") Long id,
                                      @Valid @RequestBody ArticleDTO dto) {
        adminCmsService.updateArticle(id, dto);
        return Result.success("文章更新成功", null);
    }

    @PutMapping("/articles/{id}/status")
    public Result<Void> updateArticleStatus(@PathVariable("id") Long id,
                                            @Valid @RequestBody ArticleStatusDTO dto) {
        adminCmsService.updateArticleStatus(id, dto);
        return Result.success("文章状态更新成功", null);
    }

    @DeleteMapping("/articles/{id}")
    public Result<Void> deleteArticle(@PathVariable("id") Long id) {
        adminCmsService.deleteArticle(id);
        return Result.success("文章删除成功", null);
    }
}
