package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.CommentCreateDTO;
import com.bishe.job.dto.PostCreateDTO;
import com.bishe.job.dto.PostUpdateDTO;
import com.bishe.job.service.StudentCommunityService;
import com.bishe.job.vo.PostVO;
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
@RequestMapping("/api/student")
@RequiredArgsConstructor
public class StudentCommunityController {

    private final StudentCommunityService studentCommunityService;

    @GetMapping("/posts")
    public Result<PageResult<PostVO>> listMyPosts(
            @RequestParam(value = "current", defaultValue = "1") long current,
            @RequestParam(value = "size", defaultValue = "10") long size) {
        return Result.success(studentCommunityService.listMyPosts(current, size));
    }

    @PostMapping("/posts")
    public Result<Void> createPost(@Valid @RequestBody PostCreateDTO dto) {
        studentCommunityService.createPost(dto);
        return Result.success("发布成功，等待管理员审核", null);
    }

    @PutMapping("/posts/{id}")
    public Result<Void> updatePost(@PathVariable("id") Long id,
                                  @Valid @RequestBody PostUpdateDTO dto) {
        studentCommunityService.updatePost(id, dto);
        return Result.success("修改成功，已重新提交审核", null);
    }

    @DeleteMapping("/posts/{id}")
    public Result<Void> deletePost(@PathVariable("id") Long id) {
        studentCommunityService.deletePost(id);
        return Result.success("帖子删除成功", null);
    }

    @PostMapping("/posts/{id}/comments")
    public Result<Void> addComment(@PathVariable("id") Long id,
                                   @Valid @RequestBody CommentCreateDTO dto) {
        studentCommunityService.addComment(id, dto);
        return Result.success("评论成功，等待审核", null);
    }

    @DeleteMapping("/comments/{id}")
    public Result<Void> deleteComment(@PathVariable("id") Long id) {
        studentCommunityService.deleteComment(id);
        return Result.success("评论删除成功", null);
    }
}
