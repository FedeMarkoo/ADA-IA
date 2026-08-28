package com.ada.dto

data class ChatResult(
    val content: String,
    val model: String,
    val inputTokens: Long? = null,
    val outputTokens: Long? = null,
)
