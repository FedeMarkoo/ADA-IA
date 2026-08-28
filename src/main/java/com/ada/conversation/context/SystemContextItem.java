package com.ada.conversation.context;

import com.ada.conversation.application.SystemPromptProvider;
import com.ada.conversation.application.dto.*;
import com.ada.shared.observability.MeasuredContextItem;
import lombok.RequiredArgsConstructor;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(10)
@MeasuredContextItem("system")
@RequiredArgsConstructor
public class SystemContextItem implements ContextItem {
  private final SystemPromptProvider provider;

  public LlmContentComponent component() {
    return LlmContentComponent.SYSTEM;
  }

  public ContextState apply(ChatRequest r, ContextState c) {
    var m = new java.util.ArrayList<>(c.messages());
    m.add(new LlmMessage(LlmMessageRole.SYSTEM, provider.content(), component()));
    return new ContextState(m, c.tools(), c.selection());
  }
}
