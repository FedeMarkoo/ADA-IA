package com.ada.conversation.application;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.application.port.in.RequestFilter;
import com.ada.model.application.port.out.ModelSelectionStrategy;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class SelectModelUseCase {
  private final List<RequestFilter> filters;
  private final List<ModelSelectionStrategy> strategies;

  public ModelSelection execute(ChatRequest r) {
    var current = r;
    for (var f : filters) if (f.supports(current)) current = f.apply(current);
    for (var s : strategies) if (s.supports(current)) return s.select(current);
    throw new IllegalStateException("No model selection strategy supports the request");
  }
}
