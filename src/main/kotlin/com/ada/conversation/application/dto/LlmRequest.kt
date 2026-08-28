package com.ada.conversation.application.dto

data class LlmRequest(
    val model: String,
    val messages: List<LlmMessage>,
    val tools: List<LlmTool> = emptyList(),
    val temperature: Double? = null,
    val maxTokens: Int? = null,
    val metadata: LlmRequestMetadata,
)
