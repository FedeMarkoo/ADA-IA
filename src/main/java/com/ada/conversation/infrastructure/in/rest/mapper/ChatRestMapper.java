package com.ada.conversation.infrastructure.in.rest.mapper;

import com.ada.conversation.application.dto.*; import com.ada.conversation.infrastructure.in.rest.dto.*;
import org.mapstruct.Mapper;
@Mapper(componentModel="spring") public interface ChatRestMapper { ChatRequest toApplication(ChatHttpRequest request); ChatHttpResponse toResponse(ChatResult result); default MessageStatusHttpResponse toStatus(String messageId, MessageExecutionState state) { return new MessageStatusHttpResponse(messageId, state.code(), state.detail()); } }
