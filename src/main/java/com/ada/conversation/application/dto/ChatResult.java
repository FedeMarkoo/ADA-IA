package com.ada.conversation.application.dto;

import java.util.List;

public record ChatResult(
    String messageId,
    String content,
    String model,
    Long inputTokens,
    Long outputTokens,
    List<TokenUsageComponent> tokenUsage,
    ContextSelection contextSelection,
    List<String> executedTools) {
  public ChatResult {
    tokenUsage = List.copyOf(tokenUsage);
    executedTools = List.copyOf(executedTools);
  }

  public ChatResult(String id, String c, String m, Long i, Long o) {
    this(id, c, m, i, o, List.of(), null, List.of());
  }

  public ChatResult(
      String id,
      String c,
      String m,
      Long i,
      Long o,
      List<TokenUsageComponent> usage) {
    this(id, c, m, i, o, usage, null, List.of());
  }
}
