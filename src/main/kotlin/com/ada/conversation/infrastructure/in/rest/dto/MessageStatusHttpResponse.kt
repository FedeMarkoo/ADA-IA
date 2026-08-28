package com.ada.conversation.infrastructure.`in`.rest.dto

data class MessageStatusHttpResponse(
    val messageId: String,
    val state: String,
    val detail: String? = null,
)
