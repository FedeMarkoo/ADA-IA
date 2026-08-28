package com.ada.conversation.context

import com.ada.conversation.application.ToolProvider
import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ContextContribution
import com.ada.conversation.application.dto.LlmContentComponent
import org.springframework.core.annotation.Order
import org.springframework.stereotype.Component
import com.ada.shared.observability.MeasuredContextItem

@Component
@Order(30)
@MeasuredContextItem("tools")
class ToolsContextItem(
    private val toolProviders: List<ToolProvider>,
) : ContextItem {
    override val component = LlmContentComponent.TOOLS

    override fun build(request: ChatRequest): ContextContribution = ContextContribution(
        tools = toolProviders.flatMap { it.tools() },
    )
}
