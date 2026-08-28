package com.ada.conversation.application.dto;

public record ChatResult(String messageId, String content, String model, Long inputTokens, Long outputTokens) {}
