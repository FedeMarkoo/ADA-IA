package com.ada.autonomy.infrastructure.in;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.autonomy.application.port.out.ScheduledTriggerStore;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@RequiredArgsConstructor
public class ScheduledTriggerInitializer {
  private final ScheduledTriggerStore store;
  private final AutonomyProperties properties;

  @Bean
  ApplicationRunner initializeScheduledTriggers() {
    return args -> {
      if (!properties.getWeather().isEnabled()
          || store.findAll().stream().anyMatch(trigger -> trigger.name().equals("weather.daily")))
        return;
      var zone = ZoneId.of(properties.getWeather().getTimezone());
      var cron = properties.getWeather().getCron();
      var next =
          org.springframework.scheduling.support.CronExpression.parse(cron)
              .next(Instant.now(Clock.systemUTC()).atZone(zone))
              .toInstant();
      store.save(
          new ScheduledTrigger(
              0,
              "weather.daily",
              "weather",
              cron,
              properties.getWeather().getTimezone(),
              weatherPrompt(),
              properties.getWeather().getConversationId(),
              true,
              next,
              null));
    };
  }

  private String weatherPrompt() {
    if (properties.getWeather().getPrompt() != null && !properties.getWeather().getPrompt().isBlank())
      return properties.getWeather().getPrompt();
    return "Consultá el clima actual para "
        + properties.getWeather().getLocation()
        + " y enviame un resumen breve con temperatura, sensación térmica, estado del cielo y probabilidad de lluvia.";
  }
}
