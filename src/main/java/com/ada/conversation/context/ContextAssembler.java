package com.ada.conversation.context;

import com.ada.conversation.application.dto.*;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.core.annotation.AnnotationAwareOrderComparator;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class ContextAssembler {
  private final List<ContextItem> items;

  public ContextState build(ChatRequest r) {
    var current = new ContextState();
    var ordered = new java.util.ArrayList<>(items);
    ordered.sort(AnnotationAwareOrderComparator.INSTANCE);
    for (var item : ordered) current = item.apply(r, current);
    return current;
  }
}
