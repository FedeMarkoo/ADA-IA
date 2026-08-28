package com.ada.conversation.context;

import com.ada.conversation.application.dto.*;
import com.ada.shared.observability.MeasuredContextItem;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(40)
@MeasuredContextItem("memories")
public class MemoriesContextItem implements ContextItem {
  public LlmContentComponent component() {
    return LlmContentComponent.MEMORIES;
  }

  public ContextState apply(ChatRequest r, ContextState c) {
    return c;
  }
}
