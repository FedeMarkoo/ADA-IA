package com.ada.dto

data class TokenUsageComponent(
    val component: String,
    val tokens: Long,
    val source: TokenUsageSource,
)
