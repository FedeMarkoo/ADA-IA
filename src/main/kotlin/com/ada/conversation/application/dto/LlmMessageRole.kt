package com.ada.conversation.application.dto

enum class LlmMessageRole {
    SYSTEM,
    USER,
    ASSISTANT,
    TOOL;

    fun wireName(): String = name.lowercase()
}
