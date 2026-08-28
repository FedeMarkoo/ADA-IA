package com.ada.conversation.application.dto;

public record ChatRequest(String message, String requestedModel, String conversationId) {
  public ChatRequest(String message, String requestedModel) {
    this(message, requestedModel, "default");
  }

  public ChatRequest {
    conversationId =
        conversationId == null || conversationId.isBlank() ? "default" : conversationId;
  }
}
