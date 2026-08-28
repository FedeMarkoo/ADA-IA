package com.ada.conversation.infrastructure.`in`.rest.dto

data class ChatHttpResponse(
    val content: String,
    val model: String,
    val inputTokens: Long? = null,
    val outputTokens: Long? = null,
)
