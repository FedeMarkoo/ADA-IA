package com.ada.conversation.context;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.manager.MemoryManager;
import com.ada.shared.observability.MeasuredContextItem;
import java.util.ArrayList;
import lombok.RequiredArgsConstructor;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(40)
@MeasuredContextItem("memories")
@RequiredArgsConstructor
public class MemoriesContextItem implements ContextItem {
  private final MemoryManager memoryManager;

  public LlmContentComponent component() {
    return LlmContentComponent.MEMORIES;
  }

  public ContextState apply(ChatRequest r, ContextState c) {
    var messages = new ArrayList<>(c.messages());
    var selected =
        c.selection() == null ? memoryManager.memorySubjects(r) : c.selection().memories();
    var memories = memoryManager.relevantMemories(r, selected);
    if (!memories.isEmpty()) {
      messages.add(
          new LlmMessage(
              LlmMessageRole.SYSTEM,
              "Relevant memories:\n" + String.join("\n", memories),
              component()));
    }
    return new ContextState(messages, c.tools(), c.selection());
  }
}
