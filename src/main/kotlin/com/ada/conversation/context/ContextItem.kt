package com.ada.conversation.context

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ContextState
import com.ada.conversation.application.dto.LlmContentComponent

interface ContextItem {
    val component: LlmContentComponent

    fun apply(request: ChatRequest, current: ContextState): ContextState
}
