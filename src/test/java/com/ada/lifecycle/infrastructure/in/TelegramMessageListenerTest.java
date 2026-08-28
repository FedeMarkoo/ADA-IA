package com.ada.lifecycle.infrastructure.in;

import static org.mockito.Mockito.*;

import com.ada.conversation.application.ChatUseCase;
import com.ada.conversation.application.dto.ChatResult;
import com.ada.lifecycle.infrastructure.out.telegram.TelegramBotClient;
import com.ada.lifecycle.infrastructure.out.telegram.TelegramUpdate;
import com.ada.shared.application.port.out.SecretStore;
import com.ada.shared.infrastructure.AdaProperties;
import org.junit.jupiter.api.Test;

class TelegramMessageListenerTest {
  private final ChatUseCase chatUseCase = mock(ChatUseCase.class);
  private final TelegramBotClient telegram = mock(TelegramBotClient.class);
  private final SecretStore secretStore = mock(SecretStore.class);
  private final AdaProperties properties = new AdaProperties();
  private final TelegramMessageListener listener =
      new TelegramMessageListener(chatUseCase, telegram, secretStore, properties);

  @Test
  void ignoresMessagesFromAnotherChat() {
    listener.processUpdate("token", "allowed-chat", new TelegramUpdate(1, "other-chat", "hola"));

    verifyNoInteractions(chatUseCase, telegram);
  }

  @Test
  void respondsWithTheConversationResultForTheAllowedChat() {
    when(chatUseCase.execute(any()))
        .thenReturn(new ChatResult("message-id", "respuesta", "model", null, null));

    listener.processUpdate("token", "allowed-chat", new TelegramUpdate(1, "allowed-chat", "hola"));

    verify(chatUseCase).execute(argThat(request -> request.message().equals("hola")));
    verify(telegram).sendMessage("token", "allowed-chat", "respuesta");
  }
}
