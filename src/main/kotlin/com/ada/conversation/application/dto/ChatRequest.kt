package com.ada.conversation.application.dto

data class ChatRequest(val message: String, val requestedModel: String? = null)
