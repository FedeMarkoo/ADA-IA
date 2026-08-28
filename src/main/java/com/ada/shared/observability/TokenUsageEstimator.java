package com.ada.shared.observability;

import com.ada.conversation.application.dto.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.springframework.stereotype.Component;

@Component
public class TokenUsageEstimator {
  public long estimate(ContextState c) {
    long n = 0;
    for (var m : c.messages()) n += estimateTokens(m.content());
    for (var t : c.tools())
      n += estimateTokens(t.name() + " " + t.description() + " " + t.inputSchema());
    return n;
  }

  public List<TokenUsageComponent> components(LlmRequest r) {
    var map = new LinkedHashMap<String, Long>();
    for (var m : r.messages())
      map.merge(m.component().name().toLowerCase(), estimateTokens(m.content()), Long::sum);
    long tools =
        r.tools().stream()
            .mapToLong(
                t -> estimateTokens(t.name() + " " + t.description() + " " + t.inputSchema()))
            .sum();
    if (tools > 0) map.put("tools", tools);
    var result = new ArrayList<TokenUsageComponent>();
    map.forEach((k, v) -> result.add(new TokenUsageComponent(k, v, TokenUsageSource.ESTIMATED)));
    result.add(
        new TokenUsageComponent(
            "total",
            result.stream().mapToLong(TokenUsageComponent::tokens).sum(),
            TokenUsageSource.ESTIMATED));
    return result;
  }

  private long estimateTokens(String s) {
    return (s.getBytes(StandardCharsets.UTF_8).length + 3L) / 4L;
  }
}
