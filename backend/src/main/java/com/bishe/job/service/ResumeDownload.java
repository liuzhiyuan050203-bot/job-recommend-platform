package com.bishe.job.service;

/**
 * 已通过归属校验的简历原件。
 */
public record ResumeDownload(byte[] bytes, String filename, String contentType) {
}
