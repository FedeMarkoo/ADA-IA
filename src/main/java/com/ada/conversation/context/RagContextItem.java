package com.ada.conversation.context;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.manager.RagManager;
import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.observability.MeasuredContextItem;
import java.util.ArrayList;
import lombok.RequiredArgsConstructor;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(45)
@MeasuredContextItem("rag")
@RequiredArgsConstructor
public class RagContextItem implements ContextItem {
  private final RagManager ragManager;
  private final AdaProperties properties;

  public LlmContentComponent component() {
    return LlmContentComponent.RAG;
  }

  public ContextState apply(ChatRequest request, ContextState state) {
    var documents = ragManager.retrieve(request);
    if (documents.isEmpty()) return state;
    var max = properties.getRag() == null ? 6000 : properties.getRag().getMaxContextCharacters();
    var context = new StringBuilder("Retrieved knowledge (verify against the source):\n");
    for (var document : documents) {
      var entry = "[" + document.source() + "] " + document.content() + "\n";
      if (context.length() + entry.length() > max) break;
      context.append(entry);
    }
    var messages = new ArrayList<>(state.messages());
    messages.add(new LlmMessage(LlmMessageRole.SYSTEM, context.toString(), component()));
    return new ContextState(messages, state.tools(), state.selection());
  }
}
