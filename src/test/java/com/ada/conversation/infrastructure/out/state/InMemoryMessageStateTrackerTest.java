package com.ada.conversation.infrastructure.out.state;

import static org.assertj.core.api.Assertions.assertThat;

import com.ada.conversation.application.dto.MessageExecutionState;
import java.time.Duration;
import java.util.ArrayList;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class InMemoryMessageStateTrackerTest {
  @Test
  void notifiesSubscribersWhenStateChanges() {
    var tracker = tracker();
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
    var tracker = tracker();

    assertThat(tracker.subscribe("unknown", ignored -> {})).isNull();
  }

  private InMemoryMessageStateTracker tracker() {
    var tracker = new InMemoryMessageStateTracker();
    ReflectionTestUtils.setField(tracker, "maxEntries", 10000);
    ReflectionTestUtils.setField(tracker, "ttl", Duration.ofHours(1));
    return tracker;
  }
}
