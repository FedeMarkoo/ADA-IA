package com.ada.conversation.application.port.out;

import com.ada.conversation.application.dto.MessageExecutionState;
import java.util.function.Consumer;

public interface MessageStateTracker {
  void update(String messageId, MessageExecutionState state);

  MessageExecutionState current(String messageId);

  Subscription subscribe(String messageId, Consumer<MessageExecutionState> listener);

  interface Subscription extends AutoCloseable {
    @Override
    void close();
  }
}
