package com.ada.conversation.adapters.`in`

import com.ada.conversation.application.ChatUseCase
import com.ada.dto.ChatHttpRequest
import com.ada.dto.ChatRequest
import com.ada.dto.ChatResult
import jakarta.validation.Valid
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api/v1/chat")
class ChatController(private val chatUseCase: ChatUseCase) {
    @PostMapping
    fun chat(@Valid @RequestBody request: ChatHttpRequest): ChatResult =
        chatUseCase.execute(ChatRequest(request.message, request.requestedModel))
}
