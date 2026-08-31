package com.ada.lifecycle.infrastructure.in;

import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

import com.ada.lifecycle.application.port.out.LifecycleMessageSender;
import org.junit.jupiter.api.Test;
import org.springframework.context.event.ContextClosedEvent;
import org.springframework.context.support.GenericApplicationContext;

class LifecycleNotificationListenerTest {
  private final LifecycleMessageSender sender =
      org.mockito.Mockito.mock(LifecycleMessageSender.class);
  private final LifecycleNotificationListener listener = new LifecycleNotificationListener(sender);

  @Test
  void sendsStartedMessageWhenApplicationIsReady() {
    listener.onApplicationReady(null);

    verify(sender).send("ADA inició correctamente 🚀");
  }

  @Test
  void sendsStoppingMessageWhenContextCloses() {
    listener.onContextClosed(new ContextClosedEvent(new GenericApplicationContext()));

    verify(sender).send("ADA se está apagando 📴");
  }

  @Test
  void sendsStoppingMessageOnlyOnceWhenContextClosesMoreThanOnce() {
    listener.onContextClosed(new ContextClosedEvent(new GenericApplicationContext()));
    listener.onContextClosed(new ContextClosedEvent(new GenericApplicationContext()));

    verify(sender, times(1)).send("ADA se está apagando 📴");
  }
}
