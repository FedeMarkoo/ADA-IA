package com.ada.model.infrastructure.out.litellm.dto

data class LiteLlmResponse(
    val model: String? = null,
    val choices: List<LiteLlmChoice> = emptyList(),
    val usage: LiteLlmUsage? = null,
)
