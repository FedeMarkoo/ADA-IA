package com.ada.autonomy.application.port.out;

import com.ada.autonomy.application.dto.ScheduledTrigger;
import java.util.List;

public interface ScheduledContextPreloader {
  boolean supports(String eventType);

  List<String> preload(ScheduledTrigger trigger);
}
