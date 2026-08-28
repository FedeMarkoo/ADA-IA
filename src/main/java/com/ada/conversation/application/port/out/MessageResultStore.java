package com.ada.conversation.application.port.out;

import com.ada.conversation.application.dto.ChatResult;

public interface MessageResultStore {
  void save(ChatResult result);

  ChatResult find(String messageId);
}
