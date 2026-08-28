package com.ada.conversation.application.dto;

import java.util.List;

public record LlmRequest(
    String model,
    List<LlmMessage> messages,
    List<LlmTool> tools,
    Double temperature,
    Integer maxTokens,
    LlmRequestMetadata metadata) {
  public LlmRequest {
    messages = List.copyOf(messages);
    tools = List.copyOf(tools);
  }

  public LlmRequest(String m, List<LlmMessage> ms, List<LlmTool> ts, LlmRequestMetadata md) {
    this(m, ms, ts, null, null, md);
  }
}
