package com.ada.conversation.infrastructure.in.rest.dto;

import com.ada.conversation.application.dto.TokenUsageComponent;
import java.util.List;

public record ChatHttpResponse(
    String messageId,
    String content,
    String model,
    Long inputTokens,
    Long outputTokens,
    List<TokenUsageComponent> tokenUsage) {}
