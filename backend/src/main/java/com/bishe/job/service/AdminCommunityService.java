package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.dto.AuditDTO;
import com.bishe.job.vo.CommentVO;
import com.bishe.job.vo.PostVO;

public interface AdminCommunityService {

    PageResult<PostVO> listPosts(Integer auditStatus, String keyword, long current, long size);

    void auditPost(Long id, AuditDTO dto);

    void deletePost(Long id);

    PageResult<CommentVO> listComments(Integer auditStatus, String keyword, long current, long size);

    void auditComment(Long id, AuditDTO dto);

    void deleteComment(Long id);
}
