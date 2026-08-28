package com.ada.conversation.application.dto;

import java.util.List;
public record LlmCompletion(String content,String model,Long inputTokens,Long outputTokens,List<LlmToolCall> toolCalls){ public LlmCompletion{toolCalls=List.copyOf(toolCalls);} public LlmCompletion(String c,String m,Long i,Long o){this(c,m,i,o,List.of());} }
