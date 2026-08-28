package com.ada.model.infrastructure.out.litellm.mapper;

import com.ada.conversation.application.dto.*;
import com.ada.model.infrastructure.out.litellm.dto.*;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.mapstruct.*;

@Mapper(componentModel = "spring")
public class LiteLlmMapper {
  private final ObjectMapper objectMapper = new ObjectMapper();

  public LiteLlmRequest toRequest(LlmRequest r) {
    return new LiteLlmRequest(
        r.model(),
        r.messages().stream().map(this::toMessage).toList(),
        r.tools().stream()
            .map(
                t ->
                    new LiteLlmTool(
                        "function",
                        new LiteLlmFunctionDefinition(
                            t.name(), t.description(), schema(t.inputSchema()))))
            .toList(),
        r.temperature(),
        r.maxTokens());
  }

  private LiteLlmMessage toMessage(LlmMessage m) {
    return new LiteLlmMessage(
        m.role().wireName(),
        m.content(),
        m.toolCalls().stream()
            .map(c -> new LiteLlmToolCall(c.id(), new LiteLlmFunctionCall(c.name(), c.arguments())))
            .toList(),
        m.toolCallId());
  }

  private JsonNode schema(String value) {
    try {
      return objectMapper.readTree(value);
    } catch (Exception error) {
      throw new IllegalArgumentException("Invalid tool schema", error);
    }
  }
}
