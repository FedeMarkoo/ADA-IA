package com.ada.conversation.context

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ContextContribution
import com.ada.conversation.application.dto.LlmContentComponent
import com.ada.conversation.application.dto.LlmMessage
import com.ada.conversation.application.dto.LlmMessageRole
import org.springframework.core.annotation.Order
import org.springframework.stereotype.Component
import com.ada.shared.observability.MeasuredContextItem

@Component
@Order(20)
@MeasuredContextItem("prompt")
class PromptContextItem : ContextItem {
    override val component = LlmContentComponent.PROMPT

    override fun build(request: ChatRequest): ContextContribution = ContextContribution(
        messages = listOf(LlmMessage(LlmMessageRole.USER, request.message, component)),
    )
}
