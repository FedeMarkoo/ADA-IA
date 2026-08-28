package com.ada.conversation.context

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ContextState
import com.ada.conversation.application.dto.LlmContentComponent
import org.springframework.core.annotation.Order
import org.springframework.stereotype.Component
import com.ada.shared.observability.MeasuredContextItem

@Component
@Order(50)
@MeasuredContextItem("tool_response")
class ToolResponseContextItem : ContextItem {
    override val component = LlmContentComponent.TOOL_RESPONSE

    override fun apply(request: ChatRequest, current: ContextState): ContextState = current
}
