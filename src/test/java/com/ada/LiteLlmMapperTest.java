package com.ada;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.ada.conversation.application.dto.*;
import com.ada.model.infrastructure.out.litellm.mapper.LiteLlmMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import org.junit.jupiter.api.Test;

class LiteLlmMapperTest {
  @Test
  void serializesOpenAiToolContractAndWireRole() throws Exception {
    var request =
        new LlmRequest(
            "test-model",
            List.of(new LlmMessage(LlmMessageRole.USER, "hello", LlmContentComponent.PROMPT)),
            List.of(new LlmTool("weather", "Get weather", "{\"type\":\"object\"}")),
            new LlmRequestMetadata("correlation"));

    var json = new ObjectMapper().writeValueAsString(new LiteLlmMapper().toRequest(request));

    assertTrue(json.contains("\"role\":\"user\""));
    assertTrue(json.contains("\"type\":\"function\""));
    assertTrue(json.contains("\"parameters\":{\"type\":\"object\"}"));
    assertTrue(!json.contains("input_schema"));
  }

  @Test
  void preservesToolCallIdInWireMessage() throws Exception {
    var message =
        new LlmMessage(
            LlmMessageRole.TOOL, "sunny", LlmContentComponent.TOOL_RESPONSE, List.of(), "call-1");

    var json =
        new ObjectMapper()
            .writeValueAsString(
                new LiteLlmMapper()
                    .toRequest(
                        new LlmRequest(
                            "model", List.of(message), List.of(), new LlmRequestMetadata("id"))));

    assertEquals(true, json.contains("\"tool_call_id\":\"call-1\""));
  }
}
