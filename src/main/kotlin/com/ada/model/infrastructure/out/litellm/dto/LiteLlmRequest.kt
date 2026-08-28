package com.ada.model.infrastructure.out.litellm.dto

import com.fasterxml.jackson.annotation.JsonProperty

data class LiteLlmRequest(
    val model: String,
    val messages: List<LiteLlmMessage>,
    val tools: List<LiteLlmTool> = emptyList(),
    val temperature: Double? = null,
    @JsonProperty("max_tokens") val maxTokens: Int? = null,
)
