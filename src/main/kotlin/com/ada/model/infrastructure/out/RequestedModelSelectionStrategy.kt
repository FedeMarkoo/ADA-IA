package com.ada.model.infrastructure.out

import com.ada.dto.ChatRequest
import com.ada.dto.ModelSelection
import com.ada.model.application.port.out.ModelSelectionStrategy
import org.springframework.core.annotation.Order
import org.springframework.stereotype.Component

@Component
@Order(10)
class RequestedModelSelectionStrategy : ModelSelectionStrategy {
    override fun supports(request: ChatRequest): Boolean = !request.requestedModel.isNullOrBlank()

    override fun select(request: ChatRequest): ModelSelection =
        ModelSelection(requireNotNull(request.requestedModel).trim())
}
