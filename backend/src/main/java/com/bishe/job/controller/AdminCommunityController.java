package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.AuditDTO;
import com.bishe.job.service.AdminCommunityService;
import com.bishe.job.vo.CommentVO;
import com.bishe.job.vo.PostVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin")
@RequiredArgsConstructor
public class AdminCommunityController {

    private final AdminCommunityService adminCommunityService;

    @GetMapping("/posts")
    public Result<PageResult<PostVO>> listPosts(
            @RequestParam(value = "auditStatus", required = false) Integer auditStatus,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(adminCommunityService.listPosts(auditStatus, keyword, current, size));
    }

    @PutMapping("/posts/{id}/audit")
    public Result<Void> auditPost(@PathVariable("id") Long id,
                                 @Valid @RequestBody AuditDTO dto) {
        adminCommunityService.auditPost(id, dto);
        return Result.success("帖子审核操作成功", null);
    }

    @DeleteMapping("/posts/{id}")
    public Result<Void> deletePost(@PathVariable("id") Long id) {
        adminCommunityService.deletePost(id);
        return Result.success("帖子删除成功", null);
    }

    @GetMapping("/comments")
    public Result<PageResult<CommentVO>> listComments(
            @RequestParam(value = "auditStatus", required = false) Integer auditStatus,
            @RequestParam(value = "keyword", required = false) String keyword,
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(adminCommunityService.listComments(auditStatus, keyword, current, size));
    }

    @PutMapping("/comments/{id}/audit")
    public Result<Void> auditComment(@PathVariable("id") Long id,
                                    @Valid @RequestBody AuditDTO dto) {
        adminCommunityService.auditComment(id, dto);
        return Result.success("评论审核操作成功", null);
    }

    @DeleteMapping("/comments/{id}")
    public Result<Void> deleteComment(@PathVariable("id") Long id) {
        adminCommunityService.deleteComment(id);
        return Result.success("评论删除成功", null);
    }
}
