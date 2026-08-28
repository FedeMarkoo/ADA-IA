package com.ada.conversation.infrastructure.in.rest.filter;

import com.ada.conversation.application.dto.ChatRequest; import com.ada.conversation.application.port.in.RequestFilter; import org.springframework.core.annotation.Order; import org.springframework.stereotype.Component;
@Component @Order(10) public class NormalizeChatRequestFilter implements RequestFilter { public boolean supports(ChatRequest request){return true;} public ChatRequest apply(ChatRequest request){return new ChatRequest(request.message().trim(),request.requestedModel());} }
