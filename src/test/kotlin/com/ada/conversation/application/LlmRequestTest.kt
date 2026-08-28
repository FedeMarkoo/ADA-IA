package com.ada.conversation.application

import com.ada.dto.ChatRequest
import com.ada.dto.LlmTool
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class LlmRequestTest {
    @Test
    fun `factory builds the complete request context and token breakdown`() {
        val factory = LlmRequestFactory(
            systemPromptProvider = object : SystemPromptProvider {
                override fun content(): String = "system rules"
            },
            toolProviders = listOf(
                object : ToolProvider {
                    override fun tools() = listOf(LlmTool("search", "Search data", "{}"))
                },
            ),
        )

        val request = factory.create(ChatRequest("user prompt"), "provider/model")

        assertEquals("provider/model", request.model)
        assertEquals(listOf("system", "prompt"), request.messages.map { it.component.name.lowercase() })
        assertEquals(listOf("search"), request.tools.map { it.name })
        assertEquals(
            listOf("system", "prompt", "tools", "total"),
            request.tokenComponents().map { it.component },
        )
    }
}
