package com.ada.autonomy.infrastructure.in;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.conversation.application.dto.LlmCompletion;
import com.ada.conversation.application.dto.LlmTool;
import com.ada.conversation.application.dto.LlmToolCall;
import com.ada.conversation.application.dto.ToolExecutionResult;
import com.ada.conversation.application.port.out.LlmClient;
import com.ada.conversation.manager.ToolManager;
import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.infrastructure.dto.LlmProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class ScheduledPromptContextOrchestratorTest {
  @Test
  void selectsAndExecutesMcpSubagentBeforeTheFinalModel() {
    var toolManager = org.mockito.Mockito.mock(ToolManager.class);
    var client = org.mockito.Mockito.mock(LlmClient.class);
    var properties = new AdaProperties();
    properties.setLlm(new LlmProperties("http://llm", "key", "model"));
    properties.getLlm().setRoutingModel("router");
    when(toolManager.availableTools())
        .thenReturn(List.of(new LlmTool("weather_current", "clima y pronóstico", "{}")));
    when(client.complete(any()))
        .thenReturn(new LlmCompletion("{\"tools\":[\"weather_current\"]}", "router", 1L, 1L));
    when(toolManager.execute(any(LlmToolCall.class)))
        .thenReturn(
            new ToolExecutionResult(
                "call-1",
                "weather_current",
                "{\"location\":\"La Reja, Argentina\",\"forecast\":["
                    + "{\"condition\":\"soleado\",\"min_c\":7.0,\"max_c\":20.5,\"rain_probability_pct\":0},"
                    + "{\"condition\":\"nublado\",\"min_c\":9.6,\"max_c\":20.4,\"rain_probability_pct\":20}]}"));

    var trigger =
        new ScheduledTrigger(
            1,
            "weather.daily",
            "assistant",
            "0 0 8 * * *",
            "America/Argentina/Buenos_Aires",
            "Al comenzar el día, avisame cómo estará el clima.",
            "telegram:1",
            true,
            Instant.parse("2026-08-30T10:00:00Z"),
            null);

    var context =
        new ScheduledPromptContextOrchestrator(toolManager, client, properties, new ObjectMapper())
            .preload(trigger);

    assertThat(context).hasSize(2);
    assertThat(context.get(0)).contains("CONTEXTO DE EJECUCIÓN");
    assertThat(context.get(1))
        .contains("Hoy va a estar soleado y cálido")
        .contains("Mañana, nublado y cálido")
        .contains("sin lluvias")
        .contains("lluvias leves");
    verify(toolManager).execute(any(LlmToolCall.class));
  }
}
