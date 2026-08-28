package com.ada.conversation.application.dto;

import java.util.List;

public record ContextState(
    List<LlmMessage> messages, List<LlmTool> tools, ContextSelection selection) {
  public ContextState {
    messages = List.copyOf(messages);
    tools = List.copyOf(tools);
  }

  public ContextState(List<LlmMessage> messages, List<LlmTool> tools) {
    this(messages, tools, null);
  }

  public ContextState() {
    this(List.of(), List.of(), null);
  }
}
