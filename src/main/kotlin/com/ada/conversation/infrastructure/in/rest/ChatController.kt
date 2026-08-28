package com.ada.conversation.infrastructure.`in`.rest

import com.ada.conversation.application.ChatUseCase
import com.ada.conversation.infrastructure.`in`.rest.dto.ChatHttpRequest
import com.ada.conversation.infrastructure.`in`.rest.dto.ChatHttpResponse
import com.ada.conversation.infrastructure.`in`.rest.dto.MessageStatusHttpResponse
import com.ada.conversation.infrastructure.`in`.rest.mapper.ChatRestMapper
import com.ada.conversation.application.MessageStateTracker
import jakarta.validation.Valid
import org.springframework.http.HttpStatus
import org.springframework.web.server.ResponseStatusException
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

@RestController
@RequestMapping("/api/v1/chat")
class ChatController(
    private val chatUseCase: ChatUseCase,
    private val mapper: ChatRestMapper,
    private val messageStateTracker: MessageStateTracker,
) {

    @PostMapping
    fun chat(@Valid @RequestBody request: ChatHttpRequest): ChatHttpResponse =
        mapper.toResponse(chatUseCase.execute(mapper.toApplication(request)))

    @GetMapping("/{messageId}/status")
    fun status(@PathVariable messageId: String): MessageStatusHttpResponse {
        val state = messageStateTracker.current(messageId)
            ?: throw ResponseStatusException(HttpStatus.NOT_FOUND, "Message not found")
        return mapper.toStatus(messageId, state)
    }
}
