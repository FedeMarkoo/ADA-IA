package com.ada.autonomy.infrastructure.in;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.conversation.application.dto.LlmToolCall;
import com.ada.conversation.application.dto.ToolExecutionResult;
import com.ada.conversation.application.port.out.ToolExecutor;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;

class WeatherScheduledContextPreloaderTest {
  @Test
  void includesTodayAndTomorrowWithHumanRainLabels() {
    var executor = org.mockito.Mockito.mock(ToolExecutor.class);
    when(executor.supports("weather_current")).thenReturn(true);
    when(executor.execute(any(LlmToolCall.class)))
        .thenReturn(
            new ToolExecutionResult(
                "call-1",
                "weather_current",
                "{\"location\":\"La Reja, Argentina\",\"forecast\":["
                    + "{\"condition\":\"soleado\",\"min_c\":7.0,\"max_c\":20.5,\"rain_probability_pct\":0},"
                    + "{\"condition\":\"nublado\",\"min_c\":9.6,\"max_c\":20.4,\"rain_probability_pct\":20}]}"));

    var preloader = new WeatherScheduledContextPreloader(List.of(executor), new ObjectMapper());
    var trigger =
        new ScheduledTrigger(
            1,
            "weather.daily",
            "weather",
            "0 0 8 * * *",
            "UTC",
            "clima",
            "telegram:1",
            true,
            Instant.parse("2026-08-30T10:00:00Z"),
            null);

    assertThat(preloader.preload(trigger).getFirst())
        .isEqualTo(
            "DATOS PRE-CARGADOS DEL CLIMA (no vuelvas a llamar weather_current):\n"
                + "¡Buen día! Hoy va a estar soleado y cálido en La Reja, Argentina: 7.0/20.5 °C, sin lluvias. "
                + "Mañana, nublado y cálido: 9.6/20.4 °C, lluvias leves.");
  }
}
