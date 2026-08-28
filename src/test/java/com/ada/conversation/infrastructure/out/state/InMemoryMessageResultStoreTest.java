package com.ada.conversation.infrastructure.out.state;

import static org.assertj.core.api.Assertions.assertThat;

import com.ada.conversation.application.dto.ChatResult;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

class InMemoryMessageResultStoreTest {
  @Test
  void savesAndFindsResultByMessageId() {
    var store = new InMemoryMessageResultStore();
    ReflectionTestUtils.setField(store, "ttl", Duration.ofMinutes(1));
    var result = new ChatResult("message-1", "answer", "ollama/llama3.2:1b", 2L, 3L);

    store.save(result);

    assertThat(store.find("message-1")).isEqualTo(result);
  }
}
