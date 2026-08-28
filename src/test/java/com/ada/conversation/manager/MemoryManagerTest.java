package com.ada.conversation.manager;

import static org.assertj.core.api.Assertions.assertThat;

import com.ada.conversation.application.dto.ChatRequest;
import com.ada.conversation.application.dto.LlmCompletion;
import com.ada.shared.observability.AdaMetrics;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.function.Supplier;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.test.util.ReflectionTestUtils;

class MemoryManagerTest {
  @Test
  void storesOnlyExplicitMemoryRequests() {
    var client = Mockito.mock(com.ada.conversation.application.port.out.LlmClient.class);
    Mockito.when(client.complete(Mockito.any()))
        .thenReturn(
            new LlmCompletion(
                "{\"shouldRemember\":true,\"memory\":\"prefiere respuestas breves\"}",
                "test",
                1L,
                1L));
    var manager =
        new MemoryManager(client, metricsThatExecutesMeasuredOperations(), new ObjectMapper());
    ReflectionTestUtils.setField(manager, "evaluationModel", "test");

    manager.review(new ChatRequest("Recordá que prefiero respuestas breves", null), "Entendido");

    assertThat(manager.relevantMemories(new ChatRequest("¿Qué prefiero?", null)))
        .containsExactly("prefiere respuestas breves");
  }

  @Test
  void ignoresOrdinaryConversation() {
    var client = Mockito.mock(com.ada.conversation.application.port.out.LlmClient.class);
    Mockito.when(client.complete(Mockito.any()))
        .thenReturn(
            new LlmCompletion("{\"shouldRemember\":false,\"memory\":\"\"}", "test", 1L, 1L));
    var manager =
        new MemoryManager(client, metricsThatExecutesMeasuredOperations(), new ObjectMapper());
    ReflectionTestUtils.setField(manager, "evaluationModel", "test");

    manager.review(new ChatRequest("¿Qué tiempo hace hoy?", null), "No tengo ubicación");

    assertThat(manager.relevantMemories(new ChatRequest("tiempo", null))).isEmpty();
  }

  private AdaMetrics metricsThatExecutesMeasuredOperations() {
    var metrics = Mockito.mock(AdaMetrics.class);
    Mockito.doAnswer(invocation -> ((Supplier<?>) invocation.getArgument(1)).get())
        .when(metrics)
        .measureLlm(Mockito.anyString(), Mockito.any());
    return metrics;
  }
}
