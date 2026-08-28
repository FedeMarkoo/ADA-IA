package com.ada.conversation.context;

import com.ada.conversation.application.dto.*;
import com.ada.shared.observability.MeasuredContextItem;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(70)
@MeasuredContextItem("response")
public class ResponseContextItem implements ContextItem {
  public LlmContentComponent component() {
    return LlmContentComponent.RESPONSE;
  }

  public ContextState apply(ChatRequest r, ContextState c) {
    return c;
  }
}
