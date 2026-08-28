package com.ada.conversation.infrastructure.in.rest.filter;

import com.ada.conversation.application.dto.ChatRequest; import com.ada.conversation.application.port.in.RequestFilter; import org.springframework.core.annotation.Order; import org.springframework.stereotype.Component;
@Component @Order(20) public class ValidateChatRequestFilter implements RequestFilter { public boolean supports(ChatRequest r){return r.message().isBlank();} public ChatRequest apply(ChatRequest r){throw new IllegalArgumentException("Chat message must not be blank");} }
