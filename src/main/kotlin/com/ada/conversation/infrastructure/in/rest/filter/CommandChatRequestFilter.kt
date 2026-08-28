package com.ada.conversation.infrastructure.`in`.rest.filter

import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.port.`in`.RequestFilter
import org.springframework.core.annotation.Order
import org.springframework.stereotype.Component

@Component
@Order(15)
class CommandChatRequestFilter : RequestFilter {
    override fun supports(request: ChatRequest): Boolean = request.message.startsWith("/")

    override fun apply(request: ChatRequest): ChatRequest = request
}
