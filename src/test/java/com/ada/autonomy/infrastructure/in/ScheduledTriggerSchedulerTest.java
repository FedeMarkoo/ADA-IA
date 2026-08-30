package com.ada.autonomy.infrastructure.in;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.autonomy.application.port.out.ScheduledContextPreloader;
import com.ada.autonomy.application.port.out.ScheduledTriggerStore;
import com.ada.conversation.application.ChatUseCase;
import com.ada.conversation.application.dto.ChatRequest;
import com.ada.conversation.application.dto.ChatResult;
import com.ada.lifecycle.application.port.out.LifecycleMessageSender;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class ScheduledTriggerSchedulerTest {
  private final ScheduledTriggerStore store = org.mockito.Mockito.mock(ScheduledTriggerStore.class);
  private final ChatUseCase chat = org.mockito.Mockito.mock(ChatUseCase.class);
  private final LifecycleMessageSender sender =
      org.mockito.Mockito.mock(LifecycleMessageSender.class);
  private final ScheduledContextPreloader preloader =
      org.mockito.Mockito.mock(ScheduledContextPreloader.class);
  private final ObjectMapper objectMapper = new ObjectMapper();

  @Test
  void executesTriggerAndSchedulesItsNextOccurrence() {
    var scheduler =
        new ScheduledTriggerScheduler(store, chat, sender, List.of(preloader), objectMapper);
    var now = Instant.parse("2026-08-30T10:00:00Z");
    var trigger =
        new ScheduledTrigger(
            7,
            "weather.daily",
            "weather",
            "0 0 8 * * *",
            "UTC",
            "clima",
            "telegram:1",
            true,
            now,
            null);
    org.mockito.Mockito.when(chat.execute(any()))
        .thenReturn(new ChatResult("id", "Buen día", "model", null, null));
    org.mockito.Mockito.when(preloader.supports("weather")).thenReturn(true);
    org.mockito.Mockito.when(preloader.preload(trigger)).thenReturn(List.of("weather data"));

    scheduler.run(trigger, now);

    var request = ArgumentCaptor.forClass(ChatRequest.class);
    verify(chat).execute(request.capture());
    assertThat(request.getValue().preloadedContext()).containsExactly("weather data");
    verify(sender).send("Buen día");
    verify(store).markExecuted(7, now, Instant.parse("2026-08-31T08:00:00Z"));
  }

  @Test
  void doesNothingWhenThereAreNoDueTriggers() {
    org.mockito.Mockito.when(store.findDue(any())).thenReturn(List.of());

    new ScheduledTriggerScheduler(store, chat, sender, List.of(preloader), objectMapper)
        .runDueTriggers();

    verify(store).findDue(any());
    verifyNoInteractions(chat, sender);
  }

  @Test
  void sendsPreloadedWeatherWhenModelReturnsEmptyJson() {
    var scheduler =
        new ScheduledTriggerScheduler(store, chat, sender, List.of(preloader), objectMapper);
    var now = Instant.parse("2026-08-30T10:00:00Z");
    var trigger =
        new ScheduledTrigger(
            8,
            "weather.empty",
            "weather",
            "0 0 8 * * *",
            "UTC",
            "clima",
            "telegram:1",
            true,
            now,
            null);
    org.mockito.Mockito.when(preloader.supports("weather")).thenReturn(true);
    org.mockito.Mockito.when(preloader.preload(trigger))
        .thenReturn(
            List.of(
                "DATOS PRE-CARGADOS DEL CLIMA (interno):\nClima actual en Buenos Aires: 15 °C."));
    org.mockito.Mockito.when(chat.execute(any()))
        .thenReturn(new ChatResult("id", "{}", "model", null, null));

    scheduler.run(trigger, now);

    verify(sender).send("Clima actual en Buenos Aires: 15 °C.");
  }

  @Test
  void sendsOnlyHumanTextWhenModelWrapsItInWeatherJson() {
    var scheduler =
        new ScheduledTriggerScheduler(store, chat, sender, List.of(preloader), objectMapper);
    var now = Instant.parse("2026-08-30T10:00:00Z");
    var trigger =
        new ScheduledTrigger(
            9,
            "weather.json",
            "weather",
            "0 0 8 * * *",
            "UTC",
            "clima",
            "telegram:1",
            true,
            now,
            null);
    org.mockito.Mockito.when(preloader.supports("weather")).thenReturn(true);
    org.mockito.Mockito.when(preloader.preload(trigger)).thenReturn(List.of("Clima precargado"));
    org.mockito.Mockito.when(chat.execute(any()))
        .thenReturn(
            new ChatResult(
                "id",
                "{\"Buen d\\u00eda, hoy está soleado.\": [{\"temperature\": \"22\\u00b0C\"}]}",
                "model",
                null,
                null));

    scheduler.run(trigger, now);

    verify(sender).send("Buen día, hoy está soleado.");
  }

  @Test
  void replacesNonWeatherModelTextWithTheWeatherForecast() {
    var scheduler =
        new ScheduledTriggerScheduler(store, chat, sender, List.of(preloader), objectMapper);
    var now = Instant.parse("2026-08-30T10:00:00Z");
    var trigger =
        new ScheduledTrigger(
            10,
            "weather.text",
            "weather",
            "0 0 8 * * *",
            "UTC",
            "clima",
            "telegram:1",
            true,
            now,
            null);
    org.mockito.Mockito.when(preloader.supports("weather")).thenReturn(true);
    org.mockito.Mockito.when(preloader.preload(trigger))
        .thenReturn(
            List.of(
                "DATOS PRE-CARGADOS DEL CLIMA:\n¡Buen día! 17.4 °C. Pronóstico: días agradables."));
    org.mockito.Mockito.when(chat.execute(any()))
        .thenReturn(new ChatResult("id", "saludo", "model", null, null));

    scheduler.run(trigger, now);

    verify(sender).send("¡Buen día! 17.4 °C. Pronóstico: días agradables.");
  }

  @Test
  void replacesIrrelevantModelTextWithPreloadedCalendarData() {
    var scheduler =
        new ScheduledTriggerScheduler(store, chat, sender, List.of(preloader), objectMapper);
    var now = Instant.parse("2026-08-30T10:00:00Z");
    var trigger =
        new ScheduledTrigger(
            11,
            "calendar.text",
            "assistant",
            "0 0 8 * * *",
            "UTC",
            "Avisame los próximos eventos.",
            "telegram:1",
            true,
            now,
            null);
    org.mockito.Mockito.when(preloader.supports("assistant")).thenReturn(true);
    org.mockito.Mockito.when(preloader.preload(trigger))
        .thenReturn(
            List.of(
                "CONTEXTO DE EJECUCIÓN: 08:00",
                "DATOS PRE-CARGADOS DE AGENDA (subagente calendar_upcoming_events): No hay eventos próximos."));
    org.mockito.Mockito.when(chat.execute(any()))
        .thenReturn(new ChatResult("id", "mensaje", "model", null, null));

    scheduler.run(trigger, now);

    verify(sender).send("No hay eventos próximos.");
  }
}
