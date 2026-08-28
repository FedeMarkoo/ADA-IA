package com.ada.conversation.context

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ContextState
import com.ada.conversation.application.dto.LlmMessage
import com.ada.conversation.application.dto.LlmMessageRole
import com.ada.shared.observability.TokenUsageEstimator
import org.springframework.beans.factory.annotation.Value
import com.ada.conversation.application.dto.LlmContentComponent
import org.springframework.core.annotation.Order
import org.springframework.stereotype.Component
import com.ada.shared.observability.MeasuredContextItem

@Component
@Order(60)
@MeasuredContextItem("compacted_prompt")
class CompactedPromptContextItem(
    private val tokenUsageEstimator: TokenUsageEstimator,
    @Value("\${ada.context.max-tokens:12000}") private val maxTokens: Long,
) : ContextItem {
    override val component = LlmContentComponent.COMPACTED_PROMPT

    override fun apply(request: ChatRequest, current: ContextState): ContextState {
        if (tokenUsageEstimator.estimate(current) <= maxTokens) return current

        val systemMessages = current.messages.filter { it.component == LlmContentComponent.SYSTEM }
        val messagesToCompact = current.messages.filterNot { it.component == LlmContentComponent.SYSTEM }
        val summary = messagesToCompact.joinToString("\n") { "${it.role.wireName()}: ${it.content}" }
        val compactedMessage = LlmMessage(
            LlmMessageRole.SYSTEM,
            "Previous context summary:\n$summary",
            component,
        )
        return current.copy(messages = systemMessages + compactedMessage)
    }
}
