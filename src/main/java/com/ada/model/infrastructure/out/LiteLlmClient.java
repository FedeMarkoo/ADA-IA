package com.ada.model.infrastructure.out;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.application.port.out.LlmClient;
import com.ada.conversation.application.port.out.PromptOptimizer;
import com.ada.model.infrastructure.out.litellm.dto.*;
import com.ada.model.infrastructure.out.litellm.mapper.LiteLlmMapper;
import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.observability.AdaMetrics;
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
  private final PromptOptimizer promptOptimizer;
  private RestClient client;

  @Value("${ada.llm.api-key:}")
  private String apiKey;

  @PostConstruct
  void initialize() {
    client = builder.baseUrl(properties.getLlm().getBaseUrl()).build();
  }

  public LlmCompletion complete(LlmRequest r) {
    var optimizedRequest = promptOptimizer.optimize(r);
    metrics.recordPromptOptimization(r, optimizedRequest);
    var request = client.post().uri("/v1/chat/completions").contentType(MediaType.APPLICATION_JSON);
    if (apiKey != null && !apiKey.isBlank())
      request.headers(headers -> headers.setBearerAuth(apiKey));
    var response =
        request.body(mapper.toRequest(optimizedRequest)).retrieve().body(LiteLlmResponse.class);
    if (response == null || response.choices().isEmpty())
      throw new IllegalStateException("LiteLLM returned no choices");
    var c = response.choices().getFirst();
    var calls =
        c.message().toolCalls().stream()
            .map(x -> new LlmToolCall(x.id(), x.function().name(), x.function().arguments()))
            .toList();
    var u = response.usage();
    if (u != null)
      metrics.recordProviderTokens(
          optimizedRequest.model(), u.promptTokens(), u.completionTokens());
    return new LlmCompletion(
        c.message().content() == null ? "" : c.message().content(),
        response.model() == null ? optimizedRequest.model() : response.model(),
        u == null ? null : u.promptTokens(),
        u == null ? null : u.completionTokens(),
        calls);
  }
}
