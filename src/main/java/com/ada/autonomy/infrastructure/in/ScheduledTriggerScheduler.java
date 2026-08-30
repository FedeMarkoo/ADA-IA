package com.ada.autonomy.infrastructure.in;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.autonomy.application.port.out.ScheduledContextPreloader;
import com.ada.autonomy.application.port.out.ScheduledTriggerStore;
import com.ada.conversation.application.ChatUseCase;
import com.ada.conversation.application.dto.ChatRequest;
import com.ada.lifecycle.application.port.out.LifecycleMessageSender;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
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
  private final ObjectMapper objectMapper;
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
      return preloaded.isEmpty() ? "No pude generar una respuesta." : preloadedMessage(preloaded);
    }
    var readable = readableContent(content);
    if (!preloaded.isEmpty()
        && !readable.contains("°C")
        && preloadedMessage(preloaded).contains("°C")) {
      return preloadedMessage(preloaded);
    }
    return readable;
  }

  private String readableContent(String content) {
    try {
      var json = objectMapper.readTree(content.trim());
      if (json.isTextual()) return json.asText();
      if (json.isObject()) {
        for (var fieldName : List.of("message", "text", "content", "response")) {
          var field = json.get(fieldName);
          if (field != null && field.isTextual()) return field.asText();
        }
        if (json.size() == 1) return json.fieldNames().next();
      }
    } catch (JsonProcessingException ignored) {
      // Preserve non-JSON model responses unchanged.
    }
    return content;
  }

  private String userFacing(String preloaded) {
    var separator = preloaded.indexOf('\n');
    return preloaded.startsWith("DATOS PRE-CARGADOS DEL CLIMA") && separator >= 0
        ? preloaded.substring(separator + 1)
        : preloaded;
  }

  private String preloadedMessage(List<String> preloaded) {
    return preloaded.stream()
        .map(this::userFacing)
        .filter(value -> value.contains("°C"))
        .findFirst()
        .orElseGet(() -> userFacing(preloaded.getFirst()));
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
