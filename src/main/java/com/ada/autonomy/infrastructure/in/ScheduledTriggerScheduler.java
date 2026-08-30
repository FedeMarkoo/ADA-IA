package com.ada.autonomy.infrastructure.in;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.autonomy.application.port.out.ScheduledTriggerStore;
import com.ada.conversation.application.ChatUseCase;
import com.ada.conversation.application.dto.ChatRequest;
import com.ada.lifecycle.application.port.out.LifecycleMessageSender;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class ScheduledTriggerScheduler {
  private final ScheduledTriggerStore store;
  private final ChatUseCase chatUseCase;
  private final LifecycleMessageSender messageSender;
  private final Clock clock = Clock.systemUTC();

  @Scheduled(fixedDelayString = "${ada.autonomy.scheduler.poll-ms:30000}")
  public void runDueTriggers() {
    var now = Instant.now(clock);
    for (var trigger : store.findDue(now)) run(trigger, now);
  }

  void run(ScheduledTrigger trigger, Instant now) {
    try {
      var result =
          chatUseCase.execute(
              new ChatRequest(trigger.prompt(), null, trigger.conversationId()));
      messageSender.send(result.content());
    } finally {
      store.markExecuted(trigger.id(), now, nextRun(trigger, now));
    }
  }

  private Instant nextRun(ScheduledTrigger trigger, Instant now) {
    var cron = org.springframework.scheduling.support.CronExpression.parse(trigger.cronExpression());
    var zone = ZoneId.of(trigger.timezone());
    return cron.next(now.atZone(zone)).toInstant();
  }
}
