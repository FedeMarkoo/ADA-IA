package com.ada.model.infrastructure.out.litellm.dto;

import com.fasterxml.jackson.annotation.JsonProperty; import java.util.List;
public record LiteLlmRequest(String model,List<LiteLlmMessage> messages,List<LiteLlmTool> tools,Double temperature,@JsonProperty("max_tokens") Integer maxTokens) {}
