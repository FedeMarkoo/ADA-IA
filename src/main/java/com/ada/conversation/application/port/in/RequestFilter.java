package com.ada.conversation.application.port.in;

import com.ada.conversation.application.dto.ChatRequest;

public interface RequestFilter {
  boolean supports(ChatRequest request);

  ChatRequest apply(ChatRequest request);
}
