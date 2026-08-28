package com.ada.conversation.context;

import com.ada.conversation.application.ToolProvider; import com.ada.conversation.application.dto.*; import com.ada.shared.observability.MeasuredContextItem; import java.util.List; import org.springframework.core.annotation.Order; import org.springframework.stereotype.Component;
@Component @Order(30) @MeasuredContextItem("tools") public class ToolsContextItem implements ContextItem { private final List<ToolProvider> providers; public ToolsContextItem(List<ToolProvider> p){providers=p;} public LlmContentComponent component(){return LlmContentComponent.TOOLS;} public ContextState apply(ChatRequest r,ContextState c){var t=new java.util.ArrayList<>(c.tools());providers.forEach(p->t.addAll(p.tools()));return new ContextState(c.messages(),t);} }
