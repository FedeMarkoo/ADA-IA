package com.ada.conversation.application.dto;

import java.util.List;
public record ContextState(List<LlmMessage> messages, List<LlmTool> tools) { public ContextState { messages=List.copyOf(messages); tools=List.copyOf(tools); } public ContextState(){this(List.of(),List.of());} }
