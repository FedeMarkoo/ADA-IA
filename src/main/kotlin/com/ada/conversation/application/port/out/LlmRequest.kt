package com.ada.conversation.application.port.out

enum class LlmMessageRole {
    SYSTEM,
    USER,
    ASSISTANT,
    TOOL,
}

enum class LlmContentComponent {
    SYSTEM,
    MEMORY,
    TOOLS,
    PROMPT,
    HISTORY,
}

data class LlmMessage(
    val role: LlmMessageRole,
    val content: String,
    val component: LlmContentComponent,
)

data class LlmTool(
    val name: String,
    val description: String,
    val inputSchema: String,
)

data class LlmRequestMetadata(
    val correlationId: String,
    val systemPromptVersion: String? = null,
    val filtersApplied: List<String> = emptyList(),
    val memoryIds: List<String> = emptyList(),
)

data class LlmRequest(
    val model: String,
    val messages: List<LlmMessage>,
    val tools: List<LlmTool> = emptyList(),
    val temperature: Double? = null,
    val maxTokens: Int? = null,
    val metadata: LlmRequestMetadata,
) {
    fun tokenComponents(): List<TokenUsageComponent> {
        val messageComponents = messages
            .groupingBy { it.component }
            .fold(0L) { total, message -> total + estimateTokens(message.content) }
            .map { (component, tokens) ->
                TokenUsageComponent(component.name.lowercase(), tokens, TokenUsageSource.ESTIMATED)
            }
        val toolTokens = tools.sumOf { estimateTokens("${it.name} ${it.description} ${it.inputSchema}") }
        val components = if (toolTokens == 0L) {
            messageComponents
        } else {
            messageComponents + TokenUsageComponent("tools", toolTokens, TokenUsageSource.ESTIMATED)
        }
        return components + TokenUsageComponent(
            component = "total",
            tokens = components.sumOf { it.tokens },
            source = TokenUsageSource.ESTIMATED,
        )
    }

    private fun estimateTokens(value: String): Long = (value.toByteArray().size + 3L) / 4L
}

enum class TokenUsageSource {
    ESTIMATED,
    PROVIDER,
}

data class TokenUsageComponent(
    val component: String,
    val tokens: Long,
    val source: TokenUsageSource,
)
