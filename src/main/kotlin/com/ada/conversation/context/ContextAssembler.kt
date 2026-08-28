package com.ada.conversation.context

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ContextState
import org.springframework.core.annotation.AnnotationAwareOrderComparator
import org.springframework.stereotype.Component

@Component
class ContextAssembler(
    private val contextItems: List<ContextItem>,
) {
    fun build(request: ChatRequest): ContextState = orderedItems()
        .fold(ContextState()) { current, item -> item.apply(request, current) }

    private fun orderedItems(): List<ContextItem> = contextItems.sortedWith(AnnotationAwareOrderComparator.INSTANCE)
}
