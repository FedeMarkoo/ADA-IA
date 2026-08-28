package com.ada.conversation.infrastructure.`in`.rest

import com.ada.conversation.infrastructure.`in`.rest.dto.ChatHttpRequest
import com.ada.conversation.infrastructure.`in`.rest.dto.ChatHttpResponse
import com.ada.dto.ChatRequest
import com.ada.dto.ChatResult
import org.mapstruct.Mapper

@Mapper(componentModel = "spring")
interface ChatRestMapper {
    fun toApplication(request: ChatHttpRequest): ChatRequest

    fun toResponse(result: ChatResult): ChatHttpResponse
}
