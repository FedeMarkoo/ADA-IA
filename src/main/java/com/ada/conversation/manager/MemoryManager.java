package com.ada.conversation.manager;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.application.port.out.LlmClient;
import com.ada.shared.observability.AdaMetrics;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
@Slf4j
public class MemoryManager {
  private static final String EVALUATION_SYSTEM_PROMPT =
      "Evaluate whether the interaction contains durable, useful user context. "
          + "Return only JSON with boolean shouldRemember, string subject, string memory, and string reason. "
          + "Do not remember secrets, credentials, health, financial, legal, or highly personal data. "
          + "Remember preferences, stable working conventions, and explicitly requested facts.";

  private final List<MemoryCandidate> memories = new CopyOnWriteArrayList<>();
  private final LlmClient llmClient;
  private final AdaMetrics metrics;
  private final ObjectMapper objectMapper;

  @Value("${ada.llm.default-model:unknown}")
  private String evaluationModel;

  public MemoryManager(LlmClient llmClient, AdaMetrics metrics, ObjectMapper objectMapper) {
    this.llmClient = llmClient;
    this.metrics = metrics;
    this.objectMapper = objectMapper;
  }

  public List<String> relevantMemories(ChatRequest request) {
    var query = request.message().toLowerCase();
    return memories.stream()
        .filter(memory -> memory.conversationId().equals(request.conversationId()))
        .filter(
            memory ->
                sharesMeaningfulWord(memory.subject(), query)
                    || sharesMeaningfulWord(memory.content(), query))
        .map(MemoryCandidate::content)
        .toList();
  }

  public MemoryCandidate review(ChatRequest request, String response) {
    try {
      var candidate =
          parseCandidate(evaluate(request, response).content(), request.conversationId());
      if (candidate == null || !isSafe(candidate)) return null;
      memories.removeIf(
          item ->
              item.conversationId().equals(candidate.conversationId())
                  && item.subject().equalsIgnoreCase(candidate.subject()));
      memories.add(candidate);
      return candidate;
    } catch (RuntimeException error) {
      log.warn("Memory evaluation failed; interaction will not be stored");
      return null;
    }
  }

  private LlmCompletion evaluate(ChatRequest request, String response) {
    var evaluationRequest =
        new LlmRequest(
            evaluationModel,
            List.of(
                new LlmMessage(
                    LlmMessageRole.SYSTEM, EVALUATION_SYSTEM_PROMPT, LlmContentComponent.SYSTEM),
                new LlmMessage(
                    LlmMessageRole.USER,
                    "PROMPT:\n" + request.message() + "\nRESPONSE:\n" + response,
                    LlmContentComponent.PROMPT)),
            List.of(),
            null,
            256,
            new LlmRequestMetadata("memory-evaluation"));
    var completion =
        metrics.measureLlm(evaluationModel, () -> llmClient.complete(evaluationRequest));
    metrics.recordTokenBreakdown(evaluationRequest, completion);
    return completion;
  }

  MemoryCandidate parseCandidate(String content, String conversationId) {
    try {
      var json = objectMapper.readTree(content);
      if (!json.path("shouldRemember").asBoolean(false)) return null;
      var memory = json.path("memory").asText("").trim();
      if (memory.isBlank()) return null;
      var subject = json.path("subject").asText("").trim();
      var stableSubject = subject.isBlank() ? normalize(memory) : normalize(subject);
      return new MemoryCandidate(stableSubject, memory, conversationId);
    } catch (JsonProcessingException error) {
      return null;
    }
  }

  private boolean isSafe(MemoryCandidate candidate) {
    var text = candidate.content().toLowerCase();
    return List.of(
            "password",
            "contraseña",
            "secret",
            "token",
            "api key",
            "credential",
            "tarjeta",
            "medical",
            "médic",
            "salud",
            "health",
            "financial",
            "financier",
            "finanza",
            "banco",
            "legal",
            "abogado",
            "contrato",
            "dni",
            "documento",
            "dirección",
            "domicilio")
        .stream()
        .noneMatch(text::contains);
  }

  private boolean sharesMeaningfulWord(String subject, String query) {
    return List.of(subject.toLowerCase().split("\\W+")).stream()
        .filter(word -> word.length() >= 5)
        .anyMatch(word -> query.contains(word.substring(0, Math.min(word.length(), 6))));
  }

  private String normalize(String value) {
    return value.toLowerCase().replaceAll("\\s+", " ").trim();
  }
}
