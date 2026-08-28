package com.ada.conversation.context

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ContextContribution
import com.ada.conversation.application.dto.LlmContentComponent

interface ContextItem {
    val component: LlmContentComponent

    fun build(request: ChatRequest): ContextContribution
}
