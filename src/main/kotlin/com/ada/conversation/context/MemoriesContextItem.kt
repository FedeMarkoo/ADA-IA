package com.ada.conversation.context

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ContextState
import com.ada.conversation.application.dto.LlmContentComponent
import org.springframework.core.annotation.Order
import org.springframework.stereotype.Component
import com.ada.shared.observability.MeasuredContextItem

@Component
@Order(40)
@MeasuredContextItem("memories")
class MemoriesContextItem : ContextItem {
    override val component = LlmContentComponent.MEMORIES

    override fun apply(request: ChatRequest, current: ContextState): ContextState = current
}
