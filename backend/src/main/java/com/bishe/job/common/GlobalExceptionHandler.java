package com.bishe.job.common;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.BindException;
import org.springframework.validation.BindingResult;
import org.springframework.validation.FieldError;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.NoHandlerFoundException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.List;
import java.util.stream.Collectors;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 业务异常：响应体 code 使用异常自身的 code，HTTP 状态与之对齐。
     */
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<Result<Void>> handleBusinessException(BusinessException e) {
        int code = e.getCode() == null ? 500 : e.getCode();
        if (code >= 500) {
            log.error("业务异常: code={}, msg={}", code, e.getMsg(), e);
        } else {
            log.warn("业务异常: code={}, msg={}", code, e.getMsg());
        }
        HttpStatus status = HttpStatus.resolve(code);
        if (status == null) {
            status = code >= 500 ? HttpStatus.INTERNAL_SERVER_ERROR : HttpStatus.BAD_REQUEST;
        }
        return ResponseEntity.status(status).body(Result.error(code, e.getMsg()));
    }

    /**
     * 接口不存在
     */
    @ExceptionHandler({NoResourceFoundException.class, NoHandlerFoundException.class})
    @ResponseStatus(HttpStatus.NOT_FOUND)
    public Result<Void> handleNotFoundException(Exception e) {
        log.warn("接口或资源不存在");
        return Result.error(404, "接口不存在");
    }

    /**
     * 请求方法不支持
     */
    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    @ResponseStatus(HttpStatus.METHOD_NOT_ALLOWED)
    public Result<Void> handleHttpRequestMethodNotSupportedException(HttpRequestMethodNotSupportedException e) {
        log.warn("请求方法不支持: {}", e.getMethod());
        return Result.error(405, "请求方法不支持");
    }

    /**
     * 请求体格式错误
     */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleHttpMessageNotReadableException(HttpMessageNotReadableException e) {
        log.warn("请求体不可读");
        return Result.error(400, "请求体格式错误");
    }

    /**
     * 缺少必需请求参数
     */
    @ExceptionHandler(MissingServletRequestParameterException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleMissingServletRequestParameterException(MissingServletRequestParameterException e) {
        log.warn("缺少必需请求参数: {}", e.getParameterName());
        return Result.error(400, e.getParameterName() + ": 缺少必需的请求参数");
    }

    /**
     * 参数类型不匹配
     */
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleMethodArgumentTypeMismatchException(MethodArgumentTypeMismatchException e) {
        log.warn("参数类型错误: {}", e.getName());
        return Result.error(400, e.getName() + ": 参数类型不正确");
    }

    /**
     * 请求体参数校验（@RequestBody @Valid），返回字段提示
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleMethodArgumentNotValidException(MethodArgumentNotValidException e) {
        String message = joinFieldErrors(e.getBindingResult());
        log.warn("参数校验异常: {}", message);
        return Result.error(400, message);
    }

    /**
     * 表单参数校验
     */
    @ExceptionHandler(BindException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleBindException(BindException e) {
        String message = joinFieldErrors(e.getBindingResult());
        log.warn("表单参数校验异常: {}", message);
        return Result.error(400, message);
    }

    /**
     * 路径或查询参数校验
     */
    @ExceptionHandler(ConstraintViolationException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleConstraintViolationException(ConstraintViolationException e) {
        String message = e.getConstraintViolations().stream()
                .map(this::formatViolation)
                .collect(Collectors.joining("；"));
        if (message.isBlank()) {
            message = "参数校验失败";
        }
        log.warn("约束校验异常: {}", message);
        return Result.error(400, message);
    }

    /**
     * 唯一约束冲突。具体文案由业务层优先抛出，这里只兜底且不回传 SQL。
     */
    @ExceptionHandler(DuplicateKeyException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleDuplicateKeyException(DuplicateKeyException e) {
        log.warn("唯一约束冲突");
        return Result.error(400, "数据已存在");
    }

    /**
     * 其他数据约束（检查约束等），不把数据库细节返回给前端
     */
    @ExceptionHandler(DataIntegrityViolationException.class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    public Result<Void> handleDataIntegrityViolationException(DataIntegrityViolationException e) {
        log.warn("数据约束异常");
        return Result.error(400, "提交的数据不符合约束");
    }

    /**
     * 未知异常：只记服务端日志，响应不带堆栈
     */
    @ExceptionHandler(Exception.class)
    @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
    public Result<Void> handleException(Exception e) {
        log.error("系统异常", e);
        return Result.error(500, "系统繁忙，请稍后重试");
    }

    private String joinFieldErrors(BindingResult bindingResult) {
        List<FieldError> errors = bindingResult.getFieldErrors();
        if (errors.isEmpty()) {
            return "参数校验失败";
        }
        return errors.stream()
                .map(err -> err.getField() + ": " + (err.getDefaultMessage() == null ? "不合法" : err.getDefaultMessage()))
                .collect(Collectors.joining("；"));
    }

    private String formatViolation(ConstraintViolation<?> violation) {
        String path = violation.getPropertyPath() == null ? "" : violation.getPropertyPath().toString();
        String message = violation.getMessage() == null ? "不合法" : violation.getMessage();
        if (path.isBlank()) {
            return message;
        }
        int dot = path.lastIndexOf('.');
        String field = dot >= 0 ? path.substring(dot + 1) : path;
        return field + ": " + message;
    }
}
