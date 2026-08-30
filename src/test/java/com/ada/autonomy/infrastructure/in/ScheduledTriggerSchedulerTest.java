package com.ada.autonomy.infrastructure.in;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;

import java.util.List;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.autonomy.application.port.out.ScheduledTriggerStore;
import com.ada.conversation.application.ChatUseCase;
import com.ada.conversation.application.dto.ChatResult;
import com.ada.lifecycle.application.port.out.LifecycleMessageSender;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class ScheduledTriggerSchedulerTest {
  private final ScheduledTriggerStore store = org.mockito.Mockito.mock(ScheduledTriggerStore.class);
  private final ChatUseCase chat = org.mockito.Mockito.mock(ChatUseCase.class);
  private final LifecycleMessageSender sender = org.mockito.Mockito.mock(LifecycleMessageSender.class);

  @Test
  void executesTriggerAndSchedulesItsNextOccurrence() {
    var scheduler = new ScheduledTriggerScheduler(store, chat, sender);
    var now = Instant.parse("2026-08-30T10:00:00Z");
    var trigger = new ScheduledTrigger(7, "weather.daily", "weather", "0 0 8 * * *", "UTC", "clima", "telegram:1", true, now, null);
    org.mockito.Mockito.when(chat.execute(any())).thenReturn(new ChatResult("id", "Buen día", "model", null, null));

    scheduler.run(trigger, now);

    verify(chat).execute(any());
    verify(sender).send("Buen día");
    verify(store).markExecuted(7, now, Instant.parse("2026-08-31T08:00:00Z"));
  }

  @Test
  void doesNothingWhenThereAreNoDueTriggers() {
    org.mockito.Mockito.when(store.findDue(any())).thenReturn(List.of());

    new ScheduledTriggerScheduler(store, chat, sender).runDueTriggers();

    verify(store).findDue(any());
    verifyNoInteractions(chat, sender);
  }
}
