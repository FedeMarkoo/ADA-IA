package com.ada.model.infrastructure.out.litellm.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

public record LiteLlmMessage(
    String role,
    String content,
    @JsonProperty("tool_calls") List<LiteLlmToolCall> toolCalls,
    @JsonProperty("tool_call_id") String toolCallId) {
  public LiteLlmMessage {
    toolCalls = toolCalls == null ? List.of() : List.copyOf(toolCalls);
  }

  public LiteLlmMessage(String role, String content, List<LiteLlmToolCall> toolCalls) {
    this(role, content, toolCalls, null);
  }
}
