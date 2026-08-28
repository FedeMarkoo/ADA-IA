package com.ada.conversation.infrastructure.out.state;

import static org.assertj.core.api.Assertions.assertThat;

import com.ada.conversation.application.dto.MessageExecutionState;
import java.util.ArrayList;
import org.junit.jupiter.api.Test;

class InMemoryMessageStateTrackerTest {
  @Test
  void notifiesSubscribersWhenStateChanges() {
    var tracker = new InMemoryMessageStateTracker();
    tracker.update("message-1", new MessageExecutionState.Received());
    var observed = new ArrayList<MessageExecutionState>();

    var subscription = tracker.subscribe("message-1", observed::add);
    tracker.update("message-1", new MessageExecutionState.InvokingModel("model"));
    subscription.close();
    tracker.update("message-1", new MessageExecutionState.Completed());

    assertThat(observed).containsExactly(new MessageExecutionState.InvokingModel("model"));
  }

  @Test
  void cannotSubscribeToUnknownMessage() {
    var tracker = new InMemoryMessageStateTracker();

    assertThat(tracker.subscribe("unknown", ignored -> {})).isNull();
  }
}
