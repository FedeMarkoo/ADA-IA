package com.ada.conversation.application

import com.ada.conversation.application.port.`in`.ChatRequest
import com.ada.conversation.application.port.`in`.RequestFilter
import com.ada.model.application.port.out.ModelSelection
import com.ada.model.application.port.out.ModelSelectionStrategy
import org.springframework.stereotype.Service

@Service
class SelectModelUseCase(
    private val filters: List<RequestFilter>,
    private val strategies: List<ModelSelectionStrategy>,
) {
    fun execute(request: ChatRequest): ModelSelection {
        val filteredRequest = filters
            .filter { it.supports(request) }
            .fold(request) { current, filter -> filter.apply(current) }

        return strategies
            .firstOrNull { it.supports(filteredRequest) }
            ?.select(filteredRequest)
            ?: error("No model selection strategy supports the request")
    }
}
