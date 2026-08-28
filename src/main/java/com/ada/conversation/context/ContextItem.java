package com.ada.conversation.context;

import com.ada.conversation.application.dto.*;

public interface ContextItem {
  LlmContentComponent component();

  ContextState apply(ChatRequest request, ContextState current);
}
