package com.ada.conversation.application.dto;

import java.util.List;

public record LlmMessage(
    LlmMessageRole role,
    String content,
    LlmContentComponent component,
    List<LlmToolCall> toolCalls,
    String toolCallId) {
  public LlmMessage {
    toolCalls = toolCalls == null ? List.of() : List.copyOf(toolCalls);
  }

  public LlmMessage(LlmMessageRole r, String c, LlmContentComponent x) {
    this(r, c, x, List.of(), null);
  }

  public LlmMessage(LlmMessageRole r, String c, LlmContentComponent x, List<LlmToolCall> calls) {
    this(r, c, x, calls, null);
  }
}
