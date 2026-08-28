package com.ada.conversation.application

import com.ada.dto.ChatRequest
import com.ada.dto.LlmContentComponent
import com.ada.dto.LlmMessage
import com.ada.dto.LlmMessageRole
import com.ada.dto.LlmRequest
import com.ada.dto.LlmRequestMetadata
import org.springframework.stereotype.Service
import java.util.UUID

@Service
class LlmRequestFactory(
    private val systemPromptProvider: SystemPromptProvider,
    private val toolProviders: List<ToolProvider>,
) {
    fun create(request: ChatRequest, model: String): LlmRequest = LlmRequest(
        model = model,
        messages = listOf(
            LlmMessage(LlmMessageRole.SYSTEM, systemPromptProvider.content(), LlmContentComponent.SYSTEM),
            LlmMessage(LlmMessageRole.USER, request.message, LlmContentComponent.PROMPT),
        ),
        tools = toolProviders.flatMap { it.tools() },
        metadata = LlmRequestMetadata(UUID.randomUUID().toString()),
    )
}
