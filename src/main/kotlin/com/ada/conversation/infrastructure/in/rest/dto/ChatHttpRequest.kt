package com.ada.conversation.infrastructure.in.rest.dto

import jakarta.validation.constraints.NotBlank

data class ChatHttpRequest(
    @field:NotBlank val message: String,
    val requestedModel: String? = null,
)
