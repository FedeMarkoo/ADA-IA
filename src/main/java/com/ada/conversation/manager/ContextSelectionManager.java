package com.ada.conversation.manager;

import com.ada.conversation.application.dto.*;
import com.ada.conversation.application.port.out.LlmClient;
import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.observability.AdaMetrics;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class ContextSelectionManager {
  private static final String SYSTEM_PROMPT =
      "Selecciona contexto para un asistente. Devuelve solo JSON válido: "
          + "{\"mcps\":[],\"tools\":[],\"memories\":[],\"compactContext\":false}. "
          + "Usa únicamente nombres del catálogo. No expliques nada.";

  private final LlmClient client;
  private final ToolManager toolManager;
  private final MemoryManager memoryManager;
  private final AdaProperties properties;
  private final AdaMetrics metrics;
  private final ObjectMapper objectMapper;

  public ContextSelection select(ChatRequest request) {
    var tools = toolManager.availableTools();
    var memories = memoryManager.memorySubjects(request);
    var fallback = ContextSelection.none();
    var selectionRequest = requestFor(request, tools, memories);
    try {
      var completion =
          metrics.measureStage(
              "context_selection",
              () ->
                  metrics.measureLlm(
                      properties.getLlm().getRoutingModel(),
                      () -> client.complete(selectionRequest)));
      metrics.recordTokenBreakdown(selectionRequest, completion);
      var selection = parse(completion.content(), tools, memories, fallback);
      if (isWeatherRequest(request) && !selection.tools().contains("weather_current")) {
        selection =
            new ContextSelection(
                List.of("weather"),
                List.of("weather_current"),
                selection.memories(),
                selection.compactContext());
      }
      metrics.recordContextSelection(properties.getLlm().getRoutingModel(), selection);
      return selection;
    } catch (RuntimeException error) {
      metrics.recordStageOutcome("context_selection", "fallback");
      return fallback;
    }
  }

  private LlmRequest requestFor(ChatRequest request, List<LlmTool> tools, List<String> memories) {
    var catalog =
        "MCPs: web_search (información externa), weather (clima/ubicación)\nRAG: enabled\nTools: "
            + tools.stream().map(LlmTool::name).toList()
            + "\nMemories: "
            + memories
            + "\nUser message: "
            + request.message();
    return new LlmRequest(
        properties.getLlm().getRoutingModel(),
        List.of(
            new LlmMessage(LlmMessageRole.SYSTEM, SYSTEM_PROMPT, LlmContentComponent.SYSTEM),
            new LlmMessage(LlmMessageRole.USER, catalog, LlmContentComponent.PROMPT)),
        List.of(),
        0.0,
        128,
        new LlmRequestMetadata("context-selection"));
  }

  private ContextSelection parse(
      String content, List<LlmTool> tools, List<String> memories, ContextSelection fallback) {
    try {
      JsonNode json = objectMapper.readTree(stripMarkdownFence(content));
      var validTools =
          tools.stream()
              .map(LlmTool::name)
              .filter(name -> contains(json.path("tools"), name))
              .toList();
      var validMemories =
          memories.stream().filter(name -> contains(json.path("memories"), name)).toList();
      var selectedMcps =
          List.of("web_search", "weather").stream()
              .filter(name -> contains(json.path("mcps"), name))
              .toList();
      return new ContextSelection(
          selectedMcps, validTools, validMemories, json.path("compactContext").asBoolean(false));
    } catch (Exception error) {
      return fallback;
    }
  }

  private boolean contains(JsonNode values, String expected) {
    if (!values.isArray()) return false;
    for (JsonNode value : values) if (expected.equals(value.asText())) return true;
    return false;
  }

  private String stripMarkdownFence(String content) {
    if (content == null) return "";
    var value = content.trim();
    if (!value.startsWith("```")) return value;
    var firstLineEnd = value.indexOf('\n');
    var lastFence = value.lastIndexOf("```");
    if (firstLineEnd < 0 || lastFence <= firstLineEnd) return value;
    return value.substring(firstLineEnd + 1, lastFence).trim();
  }

  private boolean isWeatherRequest(ChatRequest request) {
    var message = request.message().toLowerCase(java.util.Locale.ROOT);
    return message.contains("clima")
        || message.contains("tiempo")
        || message.contains("temperatura");
  }
}
