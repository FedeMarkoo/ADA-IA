package com.ada.autonomy.infrastructure.in.rest;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import com.ada.autonomy.application.port.out.ScheduledTriggerStore;
import com.ada.autonomy.infrastructure.in.rest.dto.ScheduledTriggerHttpRequest;
import jakarta.validation.Valid;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.scheduling.support.CronExpression;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/schedules")
@RequiredArgsConstructor
public class ScheduledTriggerController {
  private final ScheduledTriggerStore store;

  @GetMapping
  public List<ScheduledTrigger> list() {
    return store.findAll();
  }

  @PostMapping
  @ResponseStatus(HttpStatus.CREATED)
  public ScheduledTrigger create(@Valid @RequestBody ScheduledTriggerHttpRequest request) {
    try {
      var zone = ZoneId.of(request.timezone());
      var next =
          CronExpression.parse(request.cronExpression())
              .next(Instant.now(Clock.systemUTC()).atZone(zone))
              .toInstant();
      var trigger =
          new ScheduledTrigger(
              0,
              request.name(),
              request.eventType(),
              request.cronExpression(),
              request.timezone(),
              request.prompt(),
              request.conversationId(),
              request.enabled(),
              next,
              null);
      store.save(trigger);
      return store.findAll().stream()
          .filter(item -> item.name().equals(request.name()))
          .findFirst()
          .orElseThrow();
    } catch (RuntimeException exception) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid schedule", exception);
    }
  }
}
