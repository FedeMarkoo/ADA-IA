package com.ada.dto

data class LlmRequest(
    val model: String,
    val messages: List<LlmMessage>,
    val tools: List<LlmTool> = emptyList(),
    val temperature: Double? = null,
    val maxTokens: Int? = null,
    val metadata: LlmRequestMetadata,
) {
    fun tokenComponents(): List<TokenUsageComponent> {
        val messageComponents = messages.groupingBy { it.component }
            .fold(0L) { total, message -> total + estimateTokens(message.content) }
            .map { (component, tokens) ->
                TokenUsageComponent(component.name.lowercase(), tokens, TokenUsageSource.ESTIMATED)
            }
        val toolTokens = tools.sumOf { estimateTokens("${it.name} ${it.description} ${it.inputSchema}") }
        val components = if (toolTokens == 0L) messageComponents else {
            messageComponents + TokenUsageComponent("tools", toolTokens, TokenUsageSource.ESTIMATED)
        }
        return components + TokenUsageComponent("total", components.sumOf { it.tokens }, TokenUsageSource.ESTIMATED)
    }

    private fun estimateTokens(value: String): Long = (value.toByteArray().size + 3L) / 4L
}
