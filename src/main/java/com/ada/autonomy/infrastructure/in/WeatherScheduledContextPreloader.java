package com.ada.autonomy.infrastructure.in;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.autonomy.application.port.out.ScheduledContextPreloader;
import com.ada.conversation.application.dto.LlmToolCall;
import com.ada.conversation.application.port.out.ToolExecutor;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class WeatherScheduledContextPreloader implements ScheduledContextPreloader {
  private final List<ToolExecutor> executors;
  private final ObjectMapper objectMapper;

  public boolean supports(String eventType) {
    return "weather".equalsIgnoreCase(eventType);
  }

  public List<String> preload(ScheduledTrigger trigger) {
    var executor =
        executors.stream()
            .filter(candidate -> candidate.supports("weather_current"))
            .findFirst()
            .orElseThrow(() -> new IllegalStateException("Weather MCP executor is unavailable"));
    var result =
        executor.execute(new LlmToolCall(UUID.randomUUID().toString(), "weather_current", "{}"));
    return List.of(
        "DATOS PRE-CARGADOS DEL CLIMA (no vuelvas a llamar weather_current):\n"
            + readable(result.content()));
  }

  private String readable(String content) {
    try {
      var data = objectMapper.readTree(content);
      if (!data.isObject()) return content;
      return "Clima actual en "
          + data.path("location").asText("tu ubicación")
          + ": "
          + data.path("temperature_c").asText("sin temperatura")
          + " °C, sensación "
          + data.path("feels_like_c").asText("sin dato")
          + " °C, precipitación "
          + data.path("rain_probability_pct").asText("sin dato")
          + "%.";
    } catch (JsonProcessingException error) {
      return content;
    }
  }
}
