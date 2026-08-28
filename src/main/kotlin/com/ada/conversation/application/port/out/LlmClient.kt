package com.ada.conversation.application.port.out

import com.ada.conversation.application.port.`in`.ChatRequest

data class LlmCompletion(
    val content: String,
    val model: String,
    val inputTokens: Long? = null,
    val outputTokens: Long? = null,
)

interface LlmClient {
    fun complete(request: ChatRequest, model: String): LlmCompletion
}
