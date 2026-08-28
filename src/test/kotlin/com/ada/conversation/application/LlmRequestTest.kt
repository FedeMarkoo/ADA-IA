package com.ada.conversation.application

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ContextState
import com.ada.conversation.application.dto.LlmContentComponent
import com.ada.conversation.application.dto.LlmMessage
import com.ada.conversation.application.dto.LlmMessageRole
import com.ada.conversation.application.dto.LlmTool
import com.ada.conversation.context.ContextAssembler
import com.ada.conversation.context.CompactedPromptContextItem
import com.ada.conversation.context.PromptContextItem
import com.ada.conversation.context.SystemContextItem
import com.ada.conversation.context.ToolsContextItem
import com.ada.shared.observability.TokenUsageEstimator
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class LlmRequestTest {
    @Test
    fun `factory builds the complete request context and token breakdown`() {
        val contextAssembler = ContextAssembler(
            listOf(
                SystemContextItem(object : SystemPromptProvider {
                    override fun content(): String = "system rules"
                }),
                PromptContextItem(),
                ToolsContextItem(
                    listOf(object : ToolProvider {
                        override fun tools() = listOf(LlmTool("search", "Search data", "{}"))
                    }),
                ),
            ),
        )
        val factory = LlmRequestFactory(contextAssembler)

        val request = factory.create(ChatRequest("user prompt"), "provider/model")

        assertEquals("provider/model", request.model)
        assertEquals(listOf("system", "prompt"), request.messages.map { it.component.name.lowercase() })
        assertEquals(listOf("search"), request.tools.map { it.name })
        val components = TokenUsageEstimator().components(request)
        assertEquals(
            listOf("system", "prompt", "tools", "total"),
            components.map { it.component },
        )
        assertEquals(listOf(3L, 3L, 6L, 12L), components.map { it.tokens })
    }

    @Test
    fun `compactor replaces accumulated non-system context with a summary`() {
        val current = ContextState(
            messages = listOf(
                LlmMessage(LlmMessageRole.SYSTEM, "rules", LlmContentComponent.SYSTEM),
                LlmMessage(LlmMessageRole.USER, "old conversation", LlmContentComponent.PROMPT),
            ),
        )

        val compacted = CompactedPromptContextItem(TokenUsageEstimator(), maxTokens = 1)
            .apply(ChatRequest("new prompt"), current)

        assertEquals(listOf(LlmContentComponent.SYSTEM, LlmContentComponent.COMPACTED_PROMPT), compacted.messages.map { it.component })
        assertEquals("Previous context summary:\nuser: old conversation", compacted.messages.last().content)
    }
}
