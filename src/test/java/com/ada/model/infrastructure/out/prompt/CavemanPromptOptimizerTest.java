package com.ada.model.infrastructure.out.prompt;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.ada.conversation.application.dto.LlmContentComponent;
import com.ada.conversation.application.dto.LlmMessage;
import com.ada.conversation.application.dto.LlmMessageRole;
import com.ada.conversation.application.dto.LlmRequest;
import com.ada.conversation.application.dto.LlmRequestMetadata;
import java.util.List;
import org.junit.jupiter.api.Test;

class CavemanPromptOptimizerTest {
  private static final String MEMORY =
      "Relevant memories:\n"
          + "Por favor, ten en cuenta que la usuaria trabaja como fotógrafa y community manager.\n"
          + "Básicamente, prefiere respuestas cercanas, claras y profesionales.\n\n\n";

  @Test
  void compactsGeneratedMemoryContextAndKeepsFacts() {
    var request =
        request(new LlmMessage(LlmMessageRole.SYSTEM, MEMORY, LlmContentComponent.MEMORIES));

    var optimized = new CavemanPromptOptimizer(true, 0).optimize(request);

    assertEquals(
        "Relevant memories:\nla usuaria trabaja como fotógrafa y community manager.\nprefiere respuestas cercanas, claras y profesionales.",
        optimized.messages().getFirst().content());
    assertEquals(MEMORY, request.messages().getFirst().content());
  }

  @Test
  void doesNotRewriteUserPromptOrStructuredContext() {
    var user =
        new LlmMessage(
            LlmMessageRole.USER,
            "Por favor, responde conservando este JSON: {\"date\": \"2026-08-29\"}",
            LlmContentComponent.PROMPT);
    var system =
        new LlmMessage(
            LlmMessageRole.SYSTEM,
            "Por favor, conserva los valores exactos {\"id\": 42}",
            LlmContentComponent.MEMORIES);

    var optimized = new CavemanPromptOptimizer(true, 0).optimize(request(user, system));

    assertEquals(user.content(), optimized.messages().get(0).content());
    assertEquals(system.content(), optimized.messages().get(1).content());
  }

  @Test
  void disabledOptimizerReturnsOriginalRequest() {
    var request =
        request(new LlmMessage(LlmMessageRole.SYSTEM, MEMORY, LlmContentComponent.MEMORIES));

    assertEquals(request, new CavemanPromptOptimizer(false, 0).optimize(request));
  }

  @Test
  void rejectsNegativeMinimumCharacters() {
    org.junit.jupiter.api.Assertions.assertThrows(
        IllegalArgumentException.class, () -> new CavemanPromptOptimizer(true, -1));
  }

  @Test
  void preservesUndelimitedPythonAndEscapedJson() {
    var python =
        new LlmMessage(
            LlmMessageRole.SYSTEM,
            "if value == 1:\n  result = value",
            LlmContentComponent.MEMORIES);
    var json =
        new LlmMessage(
            LlmMessageRole.SYSTEM, "\\\"line\\\\nvalue\\\"", LlmContentComponent.MEMORIES);

    var optimized = new CavemanPromptOptimizer(true, 0).optimize(request(python, json));

    assertEquals(python.content(), optimized.messages().get(0).content());
    assertEquals(json.content(), optimized.messages().get(1).content());
  }

  private LlmRequest request(LlmMessage... messages) {
    return new LlmRequest("model", List.of(messages), List.of(), new LlmRequestMetadata("test"));
  }
}
