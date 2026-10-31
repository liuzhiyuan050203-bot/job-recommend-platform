package com.bishe.job.controller;

import com.bishe.job.common.PageResult;
import com.bishe.job.common.Result;
import com.bishe.job.dto.AiChatRequest;
import com.bishe.job.dto.AiSessionRenameDTO;
import com.bishe.job.service.AiChatService;
import com.bishe.job.vo.AiMessageVO;
import com.bishe.job.vo.AiSessionVO;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.util.List;

/**
 * 学生、企业、管理员各自的智能体入口。路径前缀由拦截器限制角色。
 */
@RestController
@RequestMapping("/api/{role}/ai")
@RequiredArgsConstructor
public class AiChatController {

    private final AiChatService aiChatService;

    @PostMapping("/chat/stream")
    public ResponseEntity<StreamingResponseBody> stream(@PathVariable String role,
                                                         @Valid @RequestBody AiChatRequest request,
                                                         HttpServletResponse httpResponse) {
        return aiChatService.open(role, request, httpResponse);
    }

    @GetMapping("/sessions")
    public Result<PageResult<AiSessionVO>> sessions(@PathVariable String role,
                                                     @RequestParam(value = "current", defaultValue = "1") long current,
                                                     @RequestParam(value = "size", defaultValue = "50") long size) {
        return Result.success(aiChatService.sessions(role, current, size));
    }

    @GetMapping("/sessions/{id}/messages")
    public Result<List<AiMessageVO>> messages(@PathVariable String role, @PathVariable("id") Long id) {
        return Result.success(aiChatService.messages(role, id));
    }

    @DeleteMapping("/sessions/{id}")
    public Result<Void> delete(@PathVariable String role, @PathVariable("id") Long id) {
        aiChatService.delete(role, id);
        return Result.success();
    }

    @PutMapping("/sessions/{id}")
    public Result<AiSessionVO> rename(@PathVariable String role,
                                       @PathVariable("id") Long id,
                                       @Valid @RequestBody AiSessionRenameDTO dto) {
        return Result.success(aiChatService.rename(role, id, dto));
    }
}
