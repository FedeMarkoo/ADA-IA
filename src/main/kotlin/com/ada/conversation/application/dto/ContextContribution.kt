package com.ada.conversation.application.dto

data class ContextContribution(
    val messages: List<LlmMessage> = emptyList(),
    val tools: List<LlmTool> = emptyList(),
)
