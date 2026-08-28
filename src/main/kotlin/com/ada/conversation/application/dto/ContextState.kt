package com.ada.conversation.application.dto

data class ContextState(
    val messages: List<LlmMessage> = emptyList(),
    val tools: List<LlmTool> = emptyList(),
)
