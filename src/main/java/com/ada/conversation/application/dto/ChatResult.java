package com.ada.conversation.application.dto;

import java.util.List;

public record ChatResult(
    String messageId,
    String content,
    String model,
    Long inputTokens,
    Long outputTokens,
    List<TokenUsageComponent> tokenUsage) {
  public ChatResult {
    tokenUsage = List.copyOf(tokenUsage);
  }

  public ChatResult(String id, String c, String m, Long i, Long o) {
    this(id, c, m, i, o, List.of());
  }
}
