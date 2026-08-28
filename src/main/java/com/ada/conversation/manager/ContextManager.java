package com.ada.conversation.manager;

import com.ada.conversation.application.dto.ChatRequest;
import com.ada.conversation.application.dto.ContextState;
import com.ada.conversation.context.ContextItem;
import java.util.ArrayList;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.core.annotation.AnnotationAwareOrderComparator;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class ContextManager {
  private final List<ContextItem> items;
  private final ContextSelectionManager selectionManager;

  public ContextState build(ChatRequest request) {
    var current = new ContextState(List.of(), List.of(), selectionManager.select(request));
    var orderedItems = new ArrayList<>(items);
    orderedItems.sort(AnnotationAwareOrderComparator.INSTANCE);
    for (var item : orderedItems) current = item.apply(request, current);
    return current;
  }
}
