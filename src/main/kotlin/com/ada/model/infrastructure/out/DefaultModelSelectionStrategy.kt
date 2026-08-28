package com.ada.model.infrastructure.out

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ModelSelection
import com.ada.model.application.port.out.ModelSelectionStrategy
import org.springframework.beans.factory.annotation.Value
import org.springframework.core.annotation.Order
import org.springframework.stereotype.Component

@Component
@Order(100)
class DefaultModelSelectionStrategy(
    @Value("\${ada.llm.default-model:openai/gpt-4o-mini}") private val defaultModel: String,
) : ModelSelectionStrategy {
    override fun supports(request: ChatRequest): Boolean = request.requestedModel == null

    override fun select(request: ChatRequest): ModelSelection = ModelSelection(defaultModel)
}
