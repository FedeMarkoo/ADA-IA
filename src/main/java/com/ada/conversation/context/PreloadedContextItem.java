package com.ada.conversation.context;

import com.ada.conversation.application.dto.ChatRequest;
import com.ada.conversation.application.dto.ContextState;
import com.ada.conversation.application.dto.LlmContentComponent;
import com.ada.conversation.application.dto.LlmMessage;
import com.ada.conversation.application.dto.LlmMessageRole;
import com.ada.shared.observability.MeasuredContextItem;
import java.util.ArrayList;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(15)
@MeasuredContextItem("preloaded")
public class PreloadedContextItem implements ContextItem {
  @Override
  public LlmContentComponent component() {
    return LlmContentComponent.PRELOADED;
  }

  @Override
  public ContextState apply(ChatRequest request, ContextState current) {
    if (request.preloadedContext().isEmpty()) return current;
    var messages = new ArrayList<>(current.messages());
    messages.add(
        new LlmMessage(
            LlmMessageRole.SYSTEM, String.join("\n", request.preloadedContext()), component()));
    return new ContextState(messages, current.tools(), current.selection());
  }
}
