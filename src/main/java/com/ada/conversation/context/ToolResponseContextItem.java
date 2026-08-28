package com.ada.conversation.context;

import com.ada.conversation.application.dto.*; import com.ada.shared.observability.MeasuredContextItem; import org.springframework.core.annotation.Order; import org.springframework.stereotype.Component;
@Component @Order(50) @MeasuredContextItem("tool_response") public class ToolResponseContextItem implements ContextItem { public LlmContentComponent component(){return LlmContentComponent.TOOL_RESPONSE;} public ContextState apply(ChatRequest r,ContextState c){return c;} }
