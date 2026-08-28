package com.ada.conversation.application.port.`in`

import com.ada.dto.ChatRequest

interface RequestFilter {
    /**
 * Determines whether this filter applies to the request.
 *
 * @param request The request to evaluate.
 * @return `true` if the filter applies to the request, `false` otherwise.
 */
fun supports(request: ChatRequest): Boolean

    /**
 * Applies the filter to a request.
 *
 * @param request The request to process.
 * @return The processed request.
 */
fun apply(request: ChatRequest): ChatRequest
}
