package com.ada.conversation.infrastructure.in.rest;

import com.ada.conversation.infrastructure.in.rest.dto.ErrorHttpResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.RestClientException;

@RestControllerAdvice
public class ChatExceptionHandler {
  @ExceptionHandler(IllegalArgumentException.class)
  ResponseEntity<ErrorHttpResponse> badRequest(IllegalArgumentException error) {
    return ResponseEntity.badRequest()
        .body(new ErrorHttpResponse("invalid_request", error.getMessage()));
  }

  @ExceptionHandler(RestClientException.class)
  ResponseEntity<ErrorHttpResponse> providerFailure(RestClientException error) {
    return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
        .body(new ErrorHttpResponse("llm_provider_failure", "LLM provider unavailable"));
  }

  @ExceptionHandler(RuntimeException.class)
  ResponseEntity<ErrorHttpResponse> unexpected(RuntimeException error) {
    return ResponseEntity.internalServerError()
        .body(new ErrorHttpResponse("internal_error", "Unexpected server error"));
  }
}
