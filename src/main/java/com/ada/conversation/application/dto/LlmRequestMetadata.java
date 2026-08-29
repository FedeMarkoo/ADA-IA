package com.ada.conversation.application.dto;

import java.util.List;

public record LlmRequestMetadata(
    String correlationId,
    String systemPromptVersion,
    List<String> filtersApplied,
    List<String> memoryIds,
    ContextSelection contextSelection) {
  public LlmRequestMetadata {
    filtersApplied = List.copyOf(filtersApplied);
    memoryIds = List.copyOf(memoryIds);
  }

  public LlmRequestMetadata(String c) {
    this(c, null, List.of(), List.of(), null);
  }
}
