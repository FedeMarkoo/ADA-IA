package com.ada.conversation.application.dto

data class LlmMessage(
    val role: LlmMessageRole,
    val content: String,
    val component: LlmContentComponent,
    val toolCalls: List<LlmToolCall> = emptyList(),
)
