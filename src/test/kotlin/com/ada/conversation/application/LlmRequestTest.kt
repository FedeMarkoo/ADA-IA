package com.ada.conversation.application

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.LlmTool
import com.ada.conversation.context.ContextAssembler
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
        assertEquals(
            listOf("system", "prompt", "tools", "total"),
            TokenUsageEstimator().components(request).map { it.component },
        )
    }
}
