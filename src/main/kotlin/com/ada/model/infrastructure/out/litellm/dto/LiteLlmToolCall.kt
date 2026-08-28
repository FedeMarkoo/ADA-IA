package com.ada.model.infrastructure.out.litellm.dto

data class LiteLlmToolCall(
    val id: String,
    val type: String = "function",
    val function: LiteLlmFunctionCall,
)
