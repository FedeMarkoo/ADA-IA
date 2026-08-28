package com.ada.conversation.infrastructure.out.state;

import com.ada.conversation.application.dto.ChatResult;
import com.ada.conversation.application.port.out.MessageResultStore;
import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.ConcurrentHashMap;
import lombok.NoArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
@NoArgsConstructor
public class InMemoryMessageResultStore implements MessageResultStore {
  private record Entry(ChatResult result, Instant expiresAt) {}

  private final ConcurrentHashMap<String, Entry> results = new ConcurrentHashMap<>();

  @Value("${ada.message-state.ttl:PT1H}")
  private Duration ttl;

  public void save(ChatResult result) {
    results.put(result.messageId(), new Entry(result, Instant.now().plus(ttl)));
  }

  public ChatResult find(String messageId) {
    var entry = results.get(messageId);
    if (entry == null) return null;
    if (entry.expiresAt().isBefore(Instant.now())) {
      results.remove(messageId, entry);
      return null;
    }
    return entry.result();
  }
}
