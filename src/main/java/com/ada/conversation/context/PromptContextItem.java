package com.ada.conversation.context;

import com.ada.conversation.application.dto.*; import com.ada.shared.observability.MeasuredContextItem; import org.springframework.core.annotation.Order; import org.springframework.stereotype.Component;
@Component @Order(20) @MeasuredContextItem("prompt") public class PromptContextItem implements ContextItem { public LlmContentComponent component(){return LlmContentComponent.PROMPT;} public ContextState apply(ChatRequest r,ContextState c){var m=new java.util.ArrayList<>(c.messages());m.add(new LlmMessage(LlmMessageRole.USER,r.message(),component()));return new ContextState(m,c.tools());} }
