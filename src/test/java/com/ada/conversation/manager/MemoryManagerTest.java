package com.ada.conversation.manager;

import static org.assertj.core.api.Assertions.assertThat;

import com.ada.conversation.application.dto.ChatRequest;
import org.junit.jupiter.api.Test;

class MemoryManagerTest {
  @Test
  void storesOnlyExplicitMemoryRequests() {
    var manager = new MemoryManager();

    manager.review(new ChatRequest("Recordá que prefiero respuestas breves", null), "Entendido");

    assertThat(manager.relevantMemories(new ChatRequest("¿Qué prefiero?", null)))
        .containsExactly("Entendido");
  }

  @Test
  void ignoresOrdinaryConversation() {
    var manager = new MemoryManager();

    manager.review(new ChatRequest("¿Qué tiempo hace hoy?", null), "No tengo ubicación");

    assertThat(manager.relevantMemories(new ChatRequest("tiempo", null))).isEmpty();
  }
}
