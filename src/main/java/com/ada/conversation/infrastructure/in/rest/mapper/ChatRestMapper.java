package com.ada.conversation.infrastructure.in.rest.mapper;

import com.ada.conversation.application.dto.*; import com.ada.conversation.infrastructure.in.rest.dto.*;
import org.mapstruct.Mapper; import org.mapstruct.Mapping;
@Mapper(componentModel="spring") public interface ChatRestMapper { ChatRequest toApplication(ChatHttpRequest request); ChatHttpResponse toResponse(ChatResult result); @Mapping(source="state.code",target="state") @Mapping(source="state.detail",target="detail") MessageStatusHttpResponse toStatus(String messageId,MessageExecutionState state); }
