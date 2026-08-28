package com.ada.model.infrastructure.out;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.application.port.out.LlmClient;
import com.ada.model.infrastructure.out.litellm.dto.*;
import com.ada.model.infrastructure.out.litellm.mapper.LiteLlmMapper;
import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.observability.AdaMetrics;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
@RequiredArgsConstructor
public class LiteLlmClient implements LlmClient {
  private final RestClient.Builder builder;
  private final AdaProperties properties;
  private final LiteLlmMapper mapper;
  private final AdaMetrics metrics;
  private final ObjectMapper objectMapper;
  private RestClient client;

  @Value("${ada.llm.api-key:}")
  private String apiKey;

  @PostConstruct
  void initialize() {
    client = builder.baseUrl(properties.getLlm().baseUrl()).build();
  }

  public LlmCompletion complete(LlmRequest r) {
    var request = client.post().uri("/v1/chat/completions").contentType(MediaType.APPLICATION_JSON);
    if (apiKey != null && !apiKey.isBlank())
      request.headers(headers -> headers.setBearerAuth(apiKey));
    var response = request.body(mapper.toRequest(r)).retrieve().body(LiteLlmResponse.class);
    if (response == null || response.choices().isEmpty())
      throw new IllegalStateException("LiteLLM returned no choices");
    var c = response.choices().getFirst();
    var calls =
        c.message().toolCalls().stream()
            .map(x -> new LlmToolCall(x.id(), x.function().name(), x.function().arguments()))
            .toList();
    if (calls.isEmpty()) calls = parseOllamaToolCall(c.message().content());
    var u = response.usage();
    if (u != null) metrics.recordProviderTokens(r.model(), u.promptTokens(), u.completionTokens());
    return new LlmCompletion(
        c.message().content() == null ? "" : c.message().content(),
        response.model() == null ? r.model() : response.model(),
        u == null ? null : u.promptTokens(),
        u == null ? null : u.completionTokens(),
        calls);
  }

  java.util.List<LlmToolCall> parseOllamaToolCall(String content) {
    if (content == null || content.isBlank()) return java.util.List.of();
    try {
      JsonNode node = objectMapper.readTree(content);
      if (!"function".equals(node.path("type").asText())) return java.util.List.of();
      String name = node.path("function").asText();
      JsonNode parameters = node.path("parameters");
      if (name.isBlank() || parameters.isMissingNode()) return java.util.List.of();
      return java.util.List.of(
          new LlmToolCall("ollama-" + java.util.UUID.randomUUID(), name, parameters.toString()));
    } catch (JsonProcessingException ignored) {
      return java.util.List.of();
    }
  }
}
