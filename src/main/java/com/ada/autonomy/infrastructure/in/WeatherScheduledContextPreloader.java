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
      var forecast = data.path("forecast");
      if (!forecast.isArray() || forecast.size() < 2) {
        return "¡Buen día! En " + location + " hacen " + number(data, "temperature_c") + " °C.";
      }
      var today = forecast.get(0);
      var tomorrow = forecast.get(1);
      return "¡Buen día! Hoy va a estar "
          + weatherSummary(today)
          + " en "
          + location
          + ": "
          + temperatureRange(today)
          + ", "
          + rainText(today)
          + ". Mañana, "
          + weatherSummary(tomorrow)
          + ": "
          + temperatureRange(tomorrow)
          + ", "
          + rainText(tomorrow)
          + ".";
    } catch (JsonProcessingException error) {
      return content;
    }
  }

  private String number(JsonNode data, String field) {
    return data.has(field) && data.get(field).isNumber()
        ? String.format(Locale.ROOT, "%.1f", data.get(field).asDouble())
        : "sin dato";
  }

  private String weatherSummary(JsonNode data) {
    var adjective = data.path("max_c").asDouble(0) >= 20 ? "cálido" : "templado";
    return data.path("condition").asText("variable") + " y " + adjective;
  }

  private String temperatureRange(JsonNode data) {
    return number(data, "min_c") + "/" + number(data, "max_c") + " °C";
  }

  private String rainText(JsonNode data) {
    if (!data.has("rain_probability_pct") || !data.get("rain_probability_pct").isNumber()) {
      return "sin dato";
    }
    var probability = data.get("rain_probability_pct").asInt();
    if (probability == 0) return "sin lluvias";
    if (probability <= 30) return "lluvias leves";
    if (probability <= 60) return "posibles lluvias";
    return "lluvias probables";
  }
}
