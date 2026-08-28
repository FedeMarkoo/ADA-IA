package com.ada.dto

data class LlmMessage(
    val role: LlmMessageRole,
    val content: String,
    val component: LlmContentComponent,
)
