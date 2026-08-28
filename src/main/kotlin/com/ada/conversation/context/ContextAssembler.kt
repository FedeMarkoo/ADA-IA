package com.ada.conversation.context

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ContextContribution
import org.springframework.core.annotation.AnnotationAwareOrderComparator
import org.springframework.stereotype.Component

@Component
class ContextAssembler(
    private val contextItems: List<ContextItem>,
) {
    fun build(request: ChatRequest): ContextContribution = orderedItems()
        .map { it.build(request) }
        .fold(ContextContribution()) { result, contribution ->
            ContextContribution(
                messages = result.messages + contribution.messages,
                tools = result.tools + contribution.tools,
            )
        }

    private fun orderedItems(): List<ContextItem> = contextItems.sortedWith(AnnotationAwareOrderComparator.INSTANCE)
}
