package com.ada.conversation.infrastructure.in.rest.dto;

public record ChatHttpResponse(
    String messageId, String content, String model, Long inputTokens, Long outputTokens) {}
