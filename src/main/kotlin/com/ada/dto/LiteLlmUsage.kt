package com.ada.dto

import com.fasterxml.jackson.annotation.JsonProperty

data class LiteLlmUsage(
    @JsonProperty("prompt_tokens") val promptTokens: Long? = null,
    @JsonProperty("completion_tokens") val completionTokens: Long? = null,
)
