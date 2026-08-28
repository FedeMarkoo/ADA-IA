package com.ada.model.infrastructure.out.litellm.dto

import com.fasterxml.jackson.annotation.JsonProperty

data class LiteLlmMessage(
    val role: String,
    val content: String? = null,
    @JsonProperty("tool_calls") val toolCalls: List<LiteLlmToolCall> = emptyList(),
)
