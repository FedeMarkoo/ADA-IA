package com.ada.model.application.port.out

import com.ada.conversation.application.port.`in`.ChatRequest

data class ModelSelection(val model: String)

interface ModelSelectionStrategy {
    /**
 * Determines whether this strategy applies to the specified chat request.
 *
 * @param request The chat request to evaluate.
 * @return `true` if this strategy applies to the request, `false` otherwise.
 */
fun supports(request: ChatRequest): Boolean

    /**
 * Selects a model for the given chat request.
 *
 * @param request The chat request to evaluate.
 * @return The selected model.
 */
fun select(request: ChatRequest): ModelSelection
}
