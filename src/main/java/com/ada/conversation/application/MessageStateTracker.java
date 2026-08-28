package com.ada.conversation.application;

import com.ada.conversation.application.dto.MessageExecutionState;

public interface MessageStateTracker {
  void update(String messageId, MessageExecutionState state);

  MessageExecutionState current(String messageId);
}
