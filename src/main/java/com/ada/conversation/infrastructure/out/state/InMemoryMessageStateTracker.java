package com.ada.conversation.infrastructure.out.state;

import com.ada.conversation.application.dto.MessageExecutionState;
import com.ada.conversation.application.port.out.MessageStateTracker;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class InMemoryMessageStateTracker implements MessageStateTracker {
  private record Entry(MessageExecutionState state, Instant expiresAt) {}

  private final ConcurrentHashMap<String, Entry> states = new ConcurrentHashMap<>();
  private final int maxEntries;
  private final Duration ttl;

  public InMemoryMessageStateTracker(
      @Value("${ada.message-state.max-entries:10000}") int maxEntries,
      @Value("${ada.message-state.ttl:PT1H}") Duration ttl) {
    this.maxEntries = maxEntries;
    this.ttl = ttl;
  }

  public void update(String id, MessageExecutionState s) {
    if (states.size() >= maxEntries) {
      states.entrySet().stream()
          .min(
              java.util.Map.Entry.comparingByValue(
                  java.util.Comparator.comparing(Entry::expiresAt)))
          .ifPresent(entry -> states.remove(entry.getKey()));
    }
    states.put(id, new Entry(s, Instant.now().plus(ttl)));
  }

  public MessageExecutionState current(String id) {
    var entry = states.get(id);
    if (entry == null) return null;
    if (entry.expiresAt().isBefore(Instant.now())) {
      states.remove(id, entry);
      return null;
    }
    return entry.state();
  }
}
