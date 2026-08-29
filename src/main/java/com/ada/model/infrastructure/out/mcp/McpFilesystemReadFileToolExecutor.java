package com.ada.model.infrastructure.out.mcp;

import com.ada.conversation.application.dto.LlmToolCall;
import com.ada.conversation.application.dto.ToolExecutionResult;
import com.ada.conversation.application.port.out.ToolExecutor;
import com.ada.shared.observability.AdaMetrics;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

@Component
@RequiredArgsConstructor
public class McpFilesystemReadFileToolExecutor implements ToolExecutor {
  private final RestClient.Builder builder;
  private final ObjectMapper objectMapper;
  private final AdaMetrics metrics;
  private RestClient client;

  @Value("${ada.mcp.filesystem-url:http://mcp-filesystem:8000/mcp}")
  private String endpoint;

  @jakarta.annotation.PostConstruct
  void initialize() {
    var requestFactory = new SimpleClientHttpRequestFactory();
    requestFactory.setConnectTimeout(Duration.ofSeconds(5));
    requestFactory.setReadTimeout(Duration.ofSeconds(20));
    client = builder.requestFactory(requestFactory).build();
  }

  public boolean supports(String toolName) {
    return "filesystem.read_file".equals(toolName);
  }

  public ToolExecutionResult execute(LlmToolCall call) {
    return metrics.measureMcp(call.name(), () -> executeUnmeasured(call));
  }

  private ToolExecutionResult executeUnmeasured(LlmToolCall call) {
    try {
      var arguments = objectMapper.readTree(call.arguments());
      post(
          "initialize",
          Map.of(
              "protocolVersion",
              "2024-11-05",
              "capabilities",
              Map.of(),
              "clientInfo",
              Map.of("name", "ada", "version", "1.0.0")));
      var result = post("tools/call", Map.of("name", call.name(), "arguments", arguments));
      return new ToolExecutionResult(
          call.id(), call.name(), result.path("content").path(0).path("text").asText("{}"));
    } catch (JsonProcessingException | RestClientException error) {
      throw new IllegalStateException("MCP filesystem read_file failed", error);
    }
  }

  private JsonNode post(String method, Object params) {
    var body =
        Map.of(
            "jsonrpc",
            "2.0",
            "id",
            UUID.randomUUID().toString(),
            "method",
            method,
            "params",
            params);
    var response =
        client
            .post()
            .uri(endpoint)
            .contentType(MediaType.APPLICATION_JSON)
            .body(body)
            .retrieve()
            .body(JsonNode.class);
    if (response == null || response.has("error")) {
      throw new IllegalStateException("Invalid MCP filesystem response");
    }
    return response.path("result");
  }
}
