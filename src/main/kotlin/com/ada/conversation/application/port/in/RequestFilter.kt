package com.ada.conversation.application.port.`in`

interface RequestFilter {
    fun supports(request: ChatRequest): Boolean

    fun apply(request: ChatRequest): ChatRequest
}
