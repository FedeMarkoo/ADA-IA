package com.ada.conversation.application.dto;

import java.util.List;

public record ContextSelection(
    List<String> mcps, List<String> tools, List<String> memories, boolean compactContext) {
  public ContextSelection {
    mcps = List.copyOf(mcps == null ? List.of() : mcps);
    tools = List.copyOf(tools == null ? List.of() : tools);
    memories = List.copyOf(memories == null ? List.of() : memories);
  }

  public static ContextSelection all(List<LlmTool> availableTools, List<String> availableMemories) {
    return new ContextSelection(
        List.of(), availableTools.stream().map(LlmTool::name).toList(), availableMemories, false);
  }

  public static ContextSelection none() {
    return new ContextSelection(List.of(), List.of(), List.of(), false);
  }
}
