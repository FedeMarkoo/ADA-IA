package com.ada.conversation.infrastructure.`in`.rest.mapper

import com.ada.conversation.infrastructure.`in`.rest.dto.ChatHttpRequest
import com.ada.conversation.infrastructure.`in`.rest.dto.ChatHttpResponse
import com.ada.conversation.infrastructure.`in`.rest.dto.MessageStatusHttpResponse
import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ChatResult
import com.ada.conversation.application.dto.MessageExecutionState
import org.mapstruct.Mapper
import org.mapstruct.Mapping

@Mapper(componentModel = "spring")
interface ChatRestMapper {
    fun toApplication(request: ChatHttpRequest): ChatRequest

    fun toResponse(result: ChatResult): ChatHttpResponse

    @Mapping(source = "state.code", target = "state")
    @Mapping(source = "state.detail", target = "detail")
    fun toStatus(messageId: String, state: MessageExecutionState): MessageStatusHttpResponse
}
