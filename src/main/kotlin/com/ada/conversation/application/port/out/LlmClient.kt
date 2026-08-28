package com.ada.conversation.application.port.out

data class LlmCompletion(
    val content: String,
    val model: String,
    val inputTokens: Long? = null,
    val outputTokens: Long? = null,
)

interface LlmClient {
    fun complete(request: LlmRequest): LlmCompletion
}
