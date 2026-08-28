package com.ada.conversation.application

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.LlmContentComponent
import com.ada.conversation.application.dto.LlmMessage
import com.ada.conversation.application.dto.LlmMessageRole
import com.ada.conversation.application.dto.LlmRequest
import com.ada.conversation.application.dto.LlmRequestMetadata
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
