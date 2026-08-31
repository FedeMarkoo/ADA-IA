package com.ada.autonomy.application.port.out;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import java.time.Instant;
import java.util.List;

public interface ScheduledTriggerStore {
  List<ScheduledTrigger> findDue(Instant now);

  void markExecuted(long id, Instant executedAt, Instant nextRunAt);

  void save(ScheduledTrigger trigger);

  List<ScheduledTrigger> findAll();
}
