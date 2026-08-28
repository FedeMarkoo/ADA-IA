package com.ada.conversation.application.dto

data class LlmCompletion(
    val content: String,
    val model: String,
    val inputTokens: Long? = null,
    val outputTokens: Long? = null,
)
