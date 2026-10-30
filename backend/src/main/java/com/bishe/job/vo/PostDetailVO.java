package com.bishe.job.vo;

import lombok.Data;
import lombok.EqualsAndHashCode;

import java.util.ArrayList;
import java.util.List;

@Data
@EqualsAndHashCode(callSuper = true)
public class PostDetailVO extends PostVO {

    private List<CommentVO> comments = new ArrayList<>();
}
