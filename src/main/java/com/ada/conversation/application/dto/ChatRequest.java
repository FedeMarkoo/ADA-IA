package com.ada.conversation.application.dto;

import java.util.List;

public record ChatRequest(
    String message, String requestedModel, String conversationId, List<String> preloadedContext) {
  public ChatRequest(String message, String requestedModel) {
    this(message, requestedModel, "default", List.of());
  }

  public ChatRequest(String message, String requestedModel, String conversationId) {
    this(message, requestedModel, conversationId, List.of());
  }

  public ChatRequest {
    conversationId =
        conversationId == null || conversationId.isBlank() ? "default" : conversationId;
    preloadedContext = List.copyOf(preloadedContext == null ? List.of() : preloadedContext);
  }
}
