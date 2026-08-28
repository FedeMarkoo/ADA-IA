package com.ada.conversation.application.dto

data class TokenUsageComponent(
    val component: String,
    val tokens: Long,
    val source: TokenUsageSource,
)
