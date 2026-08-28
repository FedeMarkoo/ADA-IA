package com.ada.dto

import jakarta.validation.constraints.NotBlank

data class ChatHttpRequest(
    @field:NotBlank val message: String,
    val requestedModel: String? = null,
)
