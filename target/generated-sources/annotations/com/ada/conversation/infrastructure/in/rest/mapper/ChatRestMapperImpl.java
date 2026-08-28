package com.ada.conversation.infrastructure.in.rest.mapper;

import com.ada.conversation.application.dto.ChatRequest;
import com.ada.conversation.application.dto.ChatResult;
import com.ada.conversation.infrastructure.in.rest.dto.ChatHttpRequest;
import com.ada.conversation.infrastructure.in.rest.dto.ChatHttpResponse;
import javax.annotation.processing.Generated;
import org.springframework.stereotype.Component;

@Generated(
    value = "org.mapstruct.ap.MappingProcessor",
    date = "2026-08-28T12:14:47-0300",
    comments = "version: 1.6.3, compiler: javac, environment: Java 21.0.12.1 (Eclipse Adoptium)"
)
@Component
public class ChatRestMapperImpl implements ChatRestMapper {

    @Override
    public ChatRequest toApplication(ChatHttpRequest request) {
        if ( request == null ) {
            return null;
        }

        String message = null;
        String requestedModel = null;

        message = request.message();
        requestedModel = request.requestedModel();

        ChatRequest chatRequest = new ChatRequest( message, requestedModel );

        return chatRequest;
    }

    @Override
    public ChatHttpResponse toResponse(ChatResult result) {
        if ( result == null ) {
            return null;
        }

        String content = null;
        String model = null;
        Long inputTokens = null;
        Long outputTokens = null;

        content = result.content();
        model = result.model();
        inputTokens = result.inputTokens();
        outputTokens = result.outputTokens();

        ChatHttpResponse chatHttpResponse = new ChatHttpResponse( content, model, inputTokens, outputTokens );

        return chatHttpResponse;
    }
}
