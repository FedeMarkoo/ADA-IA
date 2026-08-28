package com.ada.conversation.application

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.context.ContextAssembler
import com.ada.conversation.application.dto.LlmRequest
import com.ada.conversation.application.dto.LlmRequestMetadata
import org.springframework.stereotype.Service
import java.util.UUID

@Service
class LlmRequestFactory(
    private val contextAssembler: ContextAssembler,
) {
    fun create(request: ChatRequest, model: String): LlmRequest {
        val context = contextAssembler.build(request)
        return LlmRequest(
            model = model,
            messages = context.messages,
            tools = context.tools,
            metadata = LlmRequestMetadata(UUID.randomUUID().toString()),
        )
    }
}
