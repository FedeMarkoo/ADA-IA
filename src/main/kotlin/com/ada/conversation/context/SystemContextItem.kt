package com.ada.conversation.context

import com.ada.conversation.application.SystemPromptProvider
import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ContextState
import com.ada.conversation.application.dto.LlmContentComponent
import com.ada.conversation.application.dto.LlmMessage
import com.ada.conversation.application.dto.LlmMessageRole
import org.springframework.core.annotation.Order
import org.springframework.stereotype.Component
import com.ada.shared.observability.MeasuredContextItem

@Component
@Order(10)
@MeasuredContextItem("system")
class SystemContextItem(
    private val systemPromptProvider: SystemPromptProvider,
) : ContextItem {
    override val component = LlmContentComponent.SYSTEM

    override fun apply(request: ChatRequest, current: ContextState): ContextState = current.copy(
        messages = current.messages + LlmMessage(LlmMessageRole.SYSTEM, systemPromptProvider.content(), component),
    )
}
