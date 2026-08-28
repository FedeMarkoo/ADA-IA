package com.ada.model.infrastructure.out.litellm.dto;

public record LiteLlmToolCall(String id, String type, LiteLlmFunctionCall function) {
  public LiteLlmToolCall(String id, LiteLlmFunctionCall f) {
    this(id, "function", f);
  }
}
