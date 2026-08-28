package com.ada.model.infrastructure.out.litellm.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record LiteLlmUsage(
    @JsonProperty("prompt_tokens") Long promptTokens,
    @JsonProperty("completion_tokens") Long completionTokens) {}
