package com.ada.conversation.infrastructure.out.state;

import com.ada.conversation.application.dto.MessageExecutionState;
import com.ada.conversation.application.port.out.MessageStateTracker;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.Consumer;
import lombok.NoArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
@NoArgsConstructor
public class InMemoryMessageStateTracker implements MessageStateTracker {
  private record Entry(MessageExecutionState state, Instant expiresAt) {}

  private final ConcurrentHashMap<String, Entry> states = new ConcurrentHashMap<>();
  private final ConcurrentHashMap<String, CopyOnWriteArrayList<Consumer<MessageExecutionState>>>
      listeners = new ConcurrentHashMap<>();

  @Value("${ada.message-state.max-entries:10000}")
  private int maxEntries;

  @Value("${ada.message-state.ttl:PT1H}")
  private Duration ttl;

  public void update(String id, MessageExecutionState s) {
    if (states.size() >= maxEntries) {
      states.entrySet().stream()
          .min(
              java.util.Map.Entry.comparingByValue(
                  java.util.Comparator.comparing(Entry::expiresAt)))
          .ifPresent(entry -> states.remove(entry.getKey()));
    }
    states.put(id, new Entry(s, Instant.now().plus(ttl)));
    var messageListeners = listeners.get(id);
    if (messageListeners != null) messageListeners.forEach(listener -> listener.accept(s));
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

  @Override
  public Subscription subscribe(String id, Consumer<MessageExecutionState> listener) {
    if (current(id) == null) return null;
    var messageListeners = listeners.computeIfAbsent(id, ignored -> new CopyOnWriteArrayList<>());
    messageListeners.add(listener);
    return () -> {
      messageListeners.remove(listener);
      if (messageListeners.isEmpty()) listeners.remove(id, messageListeners);
    };
  }
}
