package com.ada.conversation.infrastructure.in.rest.filter;

import com.ada.conversation.application.dto.ChatRequest; import com.ada.conversation.application.port.in.RequestFilter; import org.springframework.core.annotation.Order; import org.springframework.stereotype.Component;
@Component @Order(15) public class CommandChatRequestFilter implements RequestFilter { public boolean supports(ChatRequest request){return request.message().startsWith("/");} public ChatRequest apply(ChatRequest request){return request;} }
