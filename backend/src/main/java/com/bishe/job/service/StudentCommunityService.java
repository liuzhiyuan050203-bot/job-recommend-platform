package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.dto.CommentCreateDTO;
import com.bishe.job.dto.PostCreateDTO;
import com.bishe.job.dto.PostUpdateDTO;
import com.bishe.job.vo.PostVO;

public interface StudentCommunityService {

    PageResult<PostVO> listMyPosts(long current, long size);

    void createPost(PostCreateDTO dto);

    void updatePost(Long id, PostUpdateDTO dto);

    void deletePost(Long id);

    void addComment(Long postId, CommentCreateDTO dto);

    void deleteComment(Long commentId);
}
