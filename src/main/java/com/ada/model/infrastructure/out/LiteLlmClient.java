package com.ada.model.infrastructure.out;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.application.port.out.LlmClient;
import com.ada.model.infrastructure.out.litellm.dto.*;
import com.ada.model.infrastructure.out.litellm.mapper.LiteLlmMapper;
import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.observability.AdaMetrics;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class LiteLlmClient implements LlmClient {
  private final RestClient client;
  private final LiteLlmMapper mapper;
  private final AdaMetrics metrics;
  private final String apiKey;

  public LiteLlmClient(RestClient.Builder b, AdaProperties p, LiteLlmMapper m, AdaMetrics a) {
    client = b.baseUrl(p.getLlm().baseUrl()).build();
    mapper = m;
    metrics = a;
    apiKey = p.getLlm().apiKey();
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
    var u = response.usage();
    if (u != null) metrics.recordProviderTokens(r.model(), u.promptTokens(), u.completionTokens());
    return new LlmCompletion(
        c.message().content() == null ? "" : c.message().content(),
        response.model() == null ? r.model() : response.model(),
        u == null ? null : u.promptTokens(),
        u == null ? null : u.completionTokens(),
        calls);
  }
}
