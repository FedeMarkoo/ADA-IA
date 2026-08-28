package com.ada.conversation.application.port.out;

import com.ada.conversation.application.dto.MessageExecutionState;

public interface MessageStateTracker {
  void update(String messageId, MessageExecutionState state);

  MessageExecutionState current(String messageId);
}
