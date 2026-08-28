package com.ada.shared.observability

import com.ada.conversation.application.dto.LlmRequest
import com.ada.conversation.application.dto.TokenUsageComponent
import com.ada.conversation.application.dto.TokenUsageSource
import org.springframework.stereotype.Component

@Component
class TokenUsageEstimator {
    fun components(request: LlmRequest): List<TokenUsageComponent> {
        val messageComponents = request.messages.groupingBy { it.component }
            .fold(0L) { total, message -> total + estimateTokens(message.content) }
            .map { (component, tokens) ->
                TokenUsageComponent(component.name.lowercase(), tokens, TokenUsageSource.ESTIMATED)
            }
        val toolTokens = request.tools.sumOf {
            estimateTokens("${it.name} ${it.description} ${it.inputSchema}")
        }
        val components = if (toolTokens == 0L) messageComponents else {
            messageComponents + TokenUsageComponent("tools", toolTokens, TokenUsageSource.ESTIMATED)
        }
        return components + TokenUsageComponent(
            "total",
            components.sumOf { it.tokens },
            TokenUsageSource.ESTIMATED,
        )
    }

    private fun estimateTokens(value: String): Long = (value.toByteArray().size + 3L) / 4L
}
