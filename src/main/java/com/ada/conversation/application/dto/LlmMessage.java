package com.ada.conversation.application.dto;

import java.util.List;

public record LlmMessage(
    LlmMessageRole role,
    String content,
    LlmContentComponent component,
    List<LlmToolCall> toolCalls) {
  public LlmMessage {
    toolCalls = List.copyOf(toolCalls);
  }

  public LlmMessage(LlmMessageRole r, String c, LlmContentComponent x) {
    this(r, c, x, List.of());
  }
}
