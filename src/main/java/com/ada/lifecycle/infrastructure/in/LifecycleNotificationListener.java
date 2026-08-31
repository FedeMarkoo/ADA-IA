package com.ada.lifecycle.infrastructure.in;

import com.ada.lifecycle.application.port.out.LifecycleMessageSender;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.ContextClosedEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

@Component
public class LifecycleNotificationListener {
  private static final String STARTED_MESSAGE = "ADA inició correctamente 🚀";
  private static final String STOPPING_MESSAGE = "ADA se está apagando 📴";

  private final List<LifecycleMessageSender> messageSenders;
  private final AtomicBoolean stoppingNotificationSent = new AtomicBoolean();

  public LifecycleNotificationListener(LifecycleMessageSender messageSender) {
    this(List.of(messageSender));
  }

  @org.springframework.beans.factory.annotation.Autowired
  public LifecycleNotificationListener(List<LifecycleMessageSender> messageSenders) {
    this.messageSenders = messageSenders;
  }

  @EventListener
  public void onApplicationReady(ApplicationReadyEvent event) {
    messageSenders.forEach(sender -> sender.send(STARTED_MESSAGE));
  }

  @EventListener
  public void onContextClosed(ContextClosedEvent event) {
    if (stoppingNotificationSent.compareAndSet(false, true)) {
      messageSenders.forEach(sender -> sender.send(STOPPING_MESSAGE));
    }
  }
}
