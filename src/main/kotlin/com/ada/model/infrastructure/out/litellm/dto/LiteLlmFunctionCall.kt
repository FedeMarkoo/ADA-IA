package com.ada.model.infrastructure.out.litellm.dto

data class LiteLlmFunctionCall(
    val name: String,
    val arguments: String,
)
