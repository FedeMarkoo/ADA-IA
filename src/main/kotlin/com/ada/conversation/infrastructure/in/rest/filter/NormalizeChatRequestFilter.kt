package com.ada.conversation.infrastructure.`in`.rest.filter

import com.ada.dto.ChatRequest
import com.ada.conversation.application.port.`in`.RequestFilter
import org.springframework.core.annotation.Order
import org.springframework.stereotype.Component

@Component
@Order(10)
class NormalizeChatRequestFilter : RequestFilter {
    override fun supports(request: ChatRequest): Boolean = true

    override fun apply(request: ChatRequest): ChatRequest = request.copy(message = request.message.trim())
}
