package com.ada.conversation.infrastructure.in.rest.dto;

public record ChatHttpResponse(String content,String model,Long inputTokens,Long outputTokens) {}
