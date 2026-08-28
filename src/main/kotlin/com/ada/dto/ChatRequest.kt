package com.ada.dto

data class ChatRequest(val message: String, val requestedModel: String? = null)
