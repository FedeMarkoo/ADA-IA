package com.ada.lifecycle.infrastructure.in;

import com.ada.lifecycle.application.port.out.LifecycleMessageSender;
import java.util.concurrent.atomic.AtomicBoolean;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.ContextClosedEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class LifecycleNotificationListener {
  private static final String STARTED_MESSAGE = "ADA inició correctamente 🚀";
  private static final String STOPPING_MESSAGE = "ADA se está apagando 📴";

  private final LifecycleMessageSender messageSender;
  private final AtomicBoolean stoppingNotificationSent = new AtomicBoolean();

  @EventListener
  public void onApplicationReady(ApplicationReadyEvent event) {
    messageSender.send(STARTED_MESSAGE);
  }

  @EventListener
  public void onContextClosed(ContextClosedEvent event) {
    if (stoppingNotificationSent.compareAndSet(false, true)) {
      messageSender.send(STOPPING_MESSAGE);
    }
  }
}
