package com.ada.conversation.adapters.`in`

import com.ada.conversation.application.ChatResult
import com.ada.conversation.application.ChatUseCase
import com.ada.conversation.application.port.`in`.ChatRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

data class ChatHttpRequest(
    @field:NotBlank val message: String,
    val requestedModel: String? = null,
)

@RestController
@RequestMapping("/api/v1/chat")
class ChatController(
    private val chatUseCase: ChatUseCase,
) {
    @PostMapping
    fun chat(@Valid @RequestBody request: ChatHttpRequest): ChatResult =
        chatUseCase.execute(ChatRequest(request.message, request.requestedModel))
}
