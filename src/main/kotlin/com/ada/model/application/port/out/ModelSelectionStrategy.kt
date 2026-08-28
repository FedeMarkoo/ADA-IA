package com.ada.model.application.port.out

import com.ada.conversation.application.port.`in`.ChatRequest

data class ModelSelection(val model: String)

interface ModelSelectionStrategy {
    fun supports(request: ChatRequest): Boolean

    fun select(request: ChatRequest): ModelSelection
}
