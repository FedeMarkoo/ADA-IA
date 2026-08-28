package com.ada;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.ada.conversation.application.dto.ChatRequest;
import org.junit.jupiter.api.Test;

class AdaApplicationTests {
  @Test
  void createsApplicationRequest() {
    var request = new ChatRequest("hello", null);

    assertEquals("hello", request.message());
  }
}
