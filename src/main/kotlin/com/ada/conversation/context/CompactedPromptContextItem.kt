package com.ada.conversation.context

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ContextContribution
import com.ada.conversation.application.dto.LlmContentComponent
import org.springframework.core.annotation.Order
import org.springframework.stereotype.Component
import com.ada.shared.observability.MeasuredContextItem

@Component
@Order(60)
@MeasuredContextItem("compacted_prompt")
class CompactedPromptContextItem : ContextItem {
    override val component = LlmContentComponent.COMPACTED_PROMPT

    override fun build(request: ChatRequest): ContextContribution = ContextContribution()
}
