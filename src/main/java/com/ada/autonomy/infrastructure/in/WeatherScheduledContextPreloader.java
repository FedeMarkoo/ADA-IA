package com.ada.autonomy.infrastructure.in;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.autonomy.application.port.out.ScheduledContextPreloader;
import com.ada.conversation.application.dto.LlmToolCall;
import com.ada.conversation.application.port.out.ToolExecutor;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.Locale;
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
      var location = data.path("location").asText("tu ubicación");
      var current =
          "Clima actual en "
              + location
              + ": "
              + number(data, "temperature_c")
              + " °C, sensación "
              + number(data, "feels_like_c")
              + " °C, precipitación "
              + data.path("rain_probability_pct").asText("sin dato")
              + "%.";
      var forecast = data.path("forecast");
      if (!forecast.isArray() || forecast.isEmpty()) return current;
      var days =
          java.util.stream.StreamSupport.stream(forecast.spliterator(), false)
              .limit(3)
              .map(
                  day ->
                      day.path("date").asText()
                          + " entre "
                          + number(day, "min_c")
                          + " y "
                          + number(day, "max_c")
                          + " °C")
              .toList();
      return "¡Buen día! " + current + " Pronóstico: " + String.join("; ", days) + ".";
    } catch (JsonProcessingException error) {
      return content;
    }
  }

  private String number(JsonNode data, String field) {
    return data.has(field) && data.get(field).isNumber()
        ? String.format(Locale.ROOT, "%.1f", data.get(field).asDouble())
        : "sin dato";
  }
}
