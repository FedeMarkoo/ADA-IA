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

  @Test
  void executesTriggerAndSchedulesItsNextOccurrence() {
    var scheduler = new ScheduledTriggerScheduler(store, chat, sender, List.of(preloader));
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

    new ScheduledTriggerScheduler(store, chat, sender, List.of(preloader)).runDueTriggers();

    verify(store).findDue(any());
    verifyNoInteractions(chat, sender);
  }
}
