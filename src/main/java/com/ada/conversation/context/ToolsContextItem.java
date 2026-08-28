package com.ada.conversation.context;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.manager.ToolManager;
import com.ada.shared.observability.MeasuredContextItem;
import lombok.RequiredArgsConstructor;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

@Component
@Order(30)
@MeasuredContextItem("tools")
@RequiredArgsConstructor
public class ToolsContextItem implements ContextItem {
  private final ToolManager toolManager;

  public LlmContentComponent component() {
    return LlmContentComponent.TOOLS;
  }

  public ContextState apply(ChatRequest r, ContextState c) {
    var selected =
        c.selection() == null
            ? toolManager.availableTools()
            : toolManager.selectedTools(c.selection().tools());
    var t = new java.util.ArrayList<>(c.tools());
    t.addAll(selected);
    return new ContextState(c.messages(), t, c.selection());
  }
}
