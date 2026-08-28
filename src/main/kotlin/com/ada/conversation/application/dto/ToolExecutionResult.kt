package com.ada.conversation.application.dto

data class ToolExecutionResult(
    val toolCallId: String,
    val toolName: String,
    val content: String,
)
