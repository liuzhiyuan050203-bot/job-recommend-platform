package com.bishe.job.service;

import com.bishe.job.common.PageResult;
import com.bishe.job.dto.AiChatRequest;
import com.bishe.job.dto.AiSessionRenameDTO;
import com.bishe.job.vo.AiMessageVO;
import com.bishe.job.vo.AiSessionVO;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.util.List;

/**
 * 三类角色的会话与 SSE 代理。身份只取登录用户，不接受客户端传入的用户编号。
 */
public interface AiChatService {

    ResponseEntity<StreamingResponseBody> open(String role, AiChatRequest request,
                                                HttpServletResponse httpResponse);

    PageResult<AiSessionVO> sessions(String role, long current, long size);

    List<AiMessageVO> messages(String role, Long sessionId);

    void delete(String role, Long sessionId);

    AiSessionVO rename(String role, Long sessionId, AiSessionRenameDTO dto);
}
