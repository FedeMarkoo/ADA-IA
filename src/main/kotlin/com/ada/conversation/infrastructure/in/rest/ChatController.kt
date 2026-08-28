package com.ada.conversation.infrastructure.`in`.rest

import com.ada.conversation.application.ChatUseCase
import com.ada.conversation.infrastructure.`in`.rest.dto.ChatHttpRequest
import com.ada.conversation.infrastructure.`in`.rest.dto.ChatHttpResponse
import jakarta.validation.Valid
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api/v1/chat")
class ChatController(
    private val chatUseCase: ChatUseCase,
    private val mapper: ChatRestMapper,
) {

    @PostMapping
    fun chat(@Valid @RequestBody request: ChatHttpRequest): ChatHttpResponse =
        mapper.toResponse(chatUseCase.execute(mapper.toApplication(request)))
}
