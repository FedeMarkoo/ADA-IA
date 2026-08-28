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
                "{\"shouldRemember\":true,\"subject\":\"respuestas\",\"memory\":\"prefiere respuestas breves\"}",
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

  @Test
  void replacesMemoryWithSameSubject() {
    var client = Mockito.mock(com.ada.conversation.application.port.out.LlmClient.class);
    Mockito.when(client.complete(Mockito.any()))
        .thenReturn(
            new LlmCompletion(
                "{\"shouldRemember\":true,\"subject\":\"respuesta\",\"memory\":\"prefiere respuestas breves\"}",
                "test",
                1L,
                1L),
            new LlmCompletion(
                "{\"shouldRemember\":true,\"subject\":\"respuesta\",\"memory\":\"prefiere respuestas detalladas\"}",
                "test",
                1L,
                1L));
    var manager = manager(client);
    var request = new ChatRequest("Recordá mi preferencia", null, "conversation-1");

    manager.review(request, "Entendido");
    manager.review(request, "Entendido");

    assertThat(manager.relevantMemories(new ChatRequest("¿Qué prefiere?", null, "conversation-1")))
        .containsExactly("prefiere respuestas detalladas");
  }

  @Test
  void isolatesMemoriesByConversation() {
    var client = Mockito.mock(com.ada.conversation.application.port.out.LlmClient.class);
    Mockito.when(client.complete(Mockito.any()))
        .thenReturn(
            new LlmCompletion(
                "{\"shouldRemember\":true,\"subject\":\"preferencia\",\"memory\":\"prefiere café\"}",
                "test",
                1L,
                1L));
    var manager = manager(client);
    manager.review(new ChatRequest("Recordá que prefiero café", null, "one"), "Ok");

    assertThat(manager.relevantMemories(new ChatRequest("¿Qué prefiero?", null, "one")))
        .containsExactly("prefiere café");
    assertThat(manager.relevantMemories(new ChatRequest("¿Qué prefiero?", null, "two"))).isEmpty();
  }

  @Test
  void rejectsSensitiveMemoryCategories() {
    var client = Mockito.mock(com.ada.conversation.application.port.out.LlmClient.class);
    Mockito.when(client.complete(Mockito.any()))
        .thenReturn(
            new LlmCompletion(
                "{\"shouldRemember\":true,\"subject\":\"dato\",\"memory\":\"tiene información médica\"}",
                "test",
                1L,
                1L),
            new LlmCompletion(
                "{\"shouldRemember\":true,\"subject\":\"dato\",\"memory\":\"tiene información financiera\"}",
                "test",
                1L,
                1L),
            new LlmCompletion(
                "{\"shouldRemember\":true,\"subject\":\"dato\",\"memory\":\"tiene un asunto legal\"}",
                "test",
                1L,
                1L));
    var manager = manager(client);

    manager.review(new ChatRequest("guardá esto", null, "medical"), "Ok");
    manager.review(new ChatRequest("guardá esto", null, "financial"), "Ok");
    manager.review(new ChatRequest("guardá esto", null, "legal"), "Ok");

    assertThat(manager.relevantMemories(new ChatRequest("dato", null, "medical"))).isEmpty();
    assertThat(manager.relevantMemories(new ChatRequest("dato", null, "financial"))).isEmpty();
    assertThat(manager.relevantMemories(new ChatRequest("dato", null, "legal"))).isEmpty();
  }

  private MemoryManager manager(com.ada.conversation.application.port.out.LlmClient client) {
    var manager =
        new MemoryManager(client, metricsThatExecutesMeasuredOperations(), new ObjectMapper());
    ReflectionTestUtils.setField(manager, "evaluationModel", "test");
    return manager;
  }

  private AdaMetrics metricsThatExecutesMeasuredOperations() {
    var metrics = Mockito.mock(AdaMetrics.class);
    Mockito.doAnswer(invocation -> ((Supplier<?>) invocation.getArgument(1)).get())
        .when(metrics)
        .measureLlm(Mockito.anyString(), Mockito.any());
    return metrics;
  }
}
