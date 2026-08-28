package com.ada.conversation.application.dto

data class LlmToolCall(
    val id: String,
    val name: String,
    val arguments: String,
)
