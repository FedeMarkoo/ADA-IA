package com.ada.autonomy.infrastructure.in;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.autonomy.application.port.out.ScheduledContextPreloader;
import com.ada.autonomy.application.port.out.ScheduledTriggerStore;
import com.ada.conversation.application.ChatUseCase;
import com.ada.conversation.application.dto.ChatRequest;
import com.ada.lifecycle.application.port.out.LifecycleMessageSender;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class ScheduledTriggerScheduler {
  private final ScheduledTriggerStore store;
  private final ChatUseCase chatUseCase;
  private final LifecycleMessageSender messageSender;
  private final List<ScheduledContextPreloader> preloaders;
  private final Clock clock = Clock.systemUTC();

  @Scheduled(fixedDelay = 1000)
  public void runDueTriggers() {
    var now = Instant.now(clock);
    for (var trigger : store.findDue(now)) run(trigger, now);
  }

  void run(ScheduledTrigger trigger, Instant now) {
    try {
      var preloaded = preload(trigger);
      var result =
          chatUseCase.execute(
              new ChatRequest(trigger.prompt(), null, trigger.conversationId(), preloaded));
      messageSender.send(safeContent(result.content(), preloaded));
    } finally {
      store.markExecuted(trigger.id(), now, nextRun(trigger, now));
    }
  }

  private String safeContent(String content, List<String> preloaded) {
    if (content == null
        || content.isBlank()
        || "{}".equals(content.trim())
        || "[]".equals(content.trim())) {
      return preloaded.isEmpty() ? "No pude generar una respuesta." : preloaded.getFirst();
    }
    return content;
  }

  private List<String> preload(ScheduledTrigger trigger) {
    return preloaders.stream()
        .filter(preloader -> preloader.supports(trigger.eventType()))
        .findFirst()
        .map(preloader -> preloader.preload(trigger))
        .orElseGet(List::of);
  }

  private Instant nextRun(ScheduledTrigger trigger, Instant now) {
    var cron =
        org.springframework.scheduling.support.CronExpression.parse(trigger.cronExpression());
    var zone = ZoneId.of(trigger.timezone());
    return cron.next(now.atZone(zone)).toInstant();
  }
}
