package com.ada.conversation.infrastructure.`in`.rest.filter

import com.ada.dto.ChatRequest
import com.ada.conversation.application.port.`in`.RequestFilter
import org.springframework.core.annotation.Order
import org.springframework.stereotype.Component

@Component
@Order(20)
class ValidateChatRequestFilter : RequestFilter {
    override fun supports(request: ChatRequest): Boolean = request.message.isBlank()

    override fun apply(request: ChatRequest): ChatRequest {
        throw IllegalArgumentException("Chat message must not be blank")
    }
}
