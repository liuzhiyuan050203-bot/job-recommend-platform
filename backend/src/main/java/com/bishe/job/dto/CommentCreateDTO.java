package com.bishe.job.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class CommentCreateDTO {

    @NotBlank(message = "评论内容不能为空")
    @Size(max = 1000, message = "评论长度最多 1000 字")
    private String content;
}
