package com.ada.autonomy.infrastructure.in;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.autonomy.application.port.out.ScheduledContextPreloader;
import com.ada.conversation.application.dto.LlmContentComponent;
import com.ada.conversation.application.dto.LlmMessage;
import com.ada.conversation.application.dto.LlmMessageRole;
import com.ada.conversation.application.dto.LlmRequest;
import com.ada.conversation.application.dto.LlmRequestMetadata;
import com.ada.conversation.application.dto.LlmTool;
import com.ada.conversation.application.dto.LlmToolCall;
import com.ada.conversation.application.dto.ToolExecutionResult;
import com.ada.conversation.application.port.out.LlmClient;
import com.ada.conversation.manager.ToolManager;
import com.ada.shared.infrastructure.AdaProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class ScheduledPromptContextOrchestrator implements ScheduledContextPreloader {
  private static final Logger log =
      LoggerFactory.getLogger(ScheduledPromptContextOrchestrator.class);
  private static final String PLANNER_PROMPT =
      "Elegí qué herramientas necesita una tarea programada. Devuelve solo JSON válido con "
          + "{\"tools\":[]}. Usa únicamente las herramientas del catálogo. Si no hace falta ninguna, "
          + "devuelve una lista vacía.";

  private final ToolManager toolManager;
  private final LlmClient client;
  private final AdaProperties properties;
  private final ObjectMapper objectMapper;

  @Override
  public boolean supports(String eventType) {
    return true;
  }

  @Override
  public List<String> preload(ScheduledTrigger trigger) {
    var selected = selectTools(trigger.prompt());
    log.info("scheduled_subagents_selected event={} tools={}", trigger.name(), selected);
    var context = new ArrayList<String>();
    context.add(executionContext(trigger));
    for (var tool : selected) {
      log.info("scheduled_subagent_start event={} tool={}", trigger.name(), tool);
      var result = toolManager.execute(new LlmToolCall(UUID.randomUUID().toString(), tool, "{}"));
      context.add(compact(tool, result));
      log.info("scheduled_subagent_done event={} tool={}", trigger.name(), tool);
    }
    return List.copyOf(context);
  }

  private List<String> selectTools(String prompt) {
    var tools = toolManager.availableTools();
    var selectionRequest =
        new LlmRequest(
            properties.getLlm().getRoutingModel(),
            List.of(
                new LlmMessage(LlmMessageRole.SYSTEM, PLANNER_PROMPT, LlmContentComponent.SYSTEM),
                new LlmMessage(
                    LlmMessageRole.USER,
                    "Catálogo: " + catalog(tools) + "\nTarea: " + prompt,
                    LlmContentComponent.PROMPT)),
            List.of(),
            0.0,
            96,
            new LlmRequestMetadata("scheduled-subagent-planner"));
    try {
      var completion = client.complete(selectionRequest);
      var selected = parseTools(completion.content(), tools);
      if (!selected.isEmpty()) return selected;
    } catch (RuntimeException error) {
      log.warn("scheduled_subagent_planner_failed; using deterministic fallback", error);
    }
    return fallbackTools(prompt, tools);
  }

  private String catalog(List<LlmTool> tools) {
    return tools.stream().map(tool -> tool.name() + ": " + tool.description()).toList().toString();
  }

  private List<String> parseTools(String content, List<LlmTool> tools) {
    try {
      var json = objectMapper.readTree(content == null ? "" : content.trim());
      var names = tools.stream().map(LlmTool::name).toList();
      var selected = new ArrayList<String>();
      for (var value : json.path("tools")) {
        if (names.contains(value.asText())) selected.add(value.asText());
      }
      return List.copyOf(selected);
    } catch (Exception error) {
      return List.of();
    }
  }

  private List<String> fallbackTools(String prompt, List<LlmTool> tools) {
    var normalized = prompt.toLowerCase(Locale.ROOT);
    return tools.stream()
        .map(LlmTool::name)
        .filter(name -> name.equals("weather_current") && containsWeather(normalized))
        .toList();
  }

  private boolean containsWeather(String prompt) {
    return prompt.contains("clima")
        || prompt.contains("tiempo")
        || prompt.contains("temperatura")
        || prompt.contains("lluvia");
  }

  private String executionContext(ScheduledTrigger trigger) {
    var localTime = ZonedDateTime.now(ZoneId.of(trigger.timezone()));
    return "CONTEXTO DE EJECUCIÓN: tarea programada a las "
        + localTime.toLocalTime().withNano(0)
        + " del "
        + localTime.toLocalDate()
        + ". Usá la hora como contexto temporal y no la repitas si no aporta valor.";
  }

  private String compact(String tool, ToolExecutionResult result) {
    if ("weather_current".equals(tool)) return weatherText(result.content());
    return "DATOS PRE-CARGADOS (subagente " + tool + "): " + result.content();
  }

  private String weatherText(String content) {
    try {
      var data = objectMapper.readTree(content);
      var location = data.path("location").asText("tu ubicación");
      var forecast = data.path("forecast");
      if (forecast.isArray() && forecast.size() >= 2) {
        return "DATOS PRE-CARGADOS DEL CLIMA (subagente weather_current; no vuelvas a llamar weather_current):\n"
            + "Hoy va a estar "
            + summary(forecast.get(0))
            + " en "
            + location
            + ": "
            + range(forecast.get(0))
            + ", "
            + rain(forecast.get(0))
            + ". Mañana, "
            + summary(forecast.get(1))
            + ": "
            + range(forecast.get(1))
            + ", "
            + rain(forecast.get(1))
            + ".";
      }
      return "DATOS PRE-CARGADOS DEL CLIMA (subagente weather_current): En "
          + location
          + " hacen "
          + data.path("temperature_c").asText("sin dato")
          + " °C.";
    } catch (Exception error) {
      return "DATOS PRE-CARGADOS (subagente weather_current): " + content;
    }
  }

  private String summary(JsonNode data) {
    return data.path("condition").asText("variable")
        + " y "
        + (data.path("max_c").asDouble(0) >= 20 ? "cálido" : "templado");
  }

  private String range(JsonNode data) {
    return number(data, "min_c") + "/" + number(data, "max_c") + " °C";
  }

  private String number(JsonNode data, String field) {
    return data.has(field) && data.get(field).isNumber()
        ? String.format(Locale.ROOT, "%.1f", data.get(field).asDouble())
        : "sin dato";
  }

  private String rain(JsonNode data) {
    if (!data.has("rain_probability_pct") || !data.get("rain_probability_pct").isNumber()) {
      return "sin lluvias";
    }
    var probability = data.get("rain_probability_pct").asInt();
    if (probability == 0) return "sin lluvias";
    if (probability <= 30) return "lluvias leves";
    if (probability <= 60) return "posibles lluvias";
    return "lluvias probables";
  }
}
