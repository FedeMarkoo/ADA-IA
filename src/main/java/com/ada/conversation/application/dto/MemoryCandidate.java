package com.ada.conversation.application.dto;

public record MemoryCandidate(String subject, String content, String conversationId) {
  public MemoryCandidate(String subject, String content) {
    this(subject, content, "default");
  }
}
