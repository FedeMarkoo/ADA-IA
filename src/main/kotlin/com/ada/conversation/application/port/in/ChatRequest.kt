package com.ada.conversation.application.port.`in`

data class ChatRequest(
    val message: String,
    val requestedModel: String? = null,
)
