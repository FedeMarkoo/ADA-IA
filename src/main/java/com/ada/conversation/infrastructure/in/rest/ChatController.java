package com.ada.conversation.infrastructure.in.rest;

import com.ada.conversation.application.*;
import com.ada.conversation.infrastructure.in.rest.dto.*;
import com.ada.conversation.infrastructure.in.rest.mapper.ChatRestMapper;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/chat")
public class ChatController {
  private final ChatUseCase useCase;
  private final ChatRestMapper mapper;
  private final MessageStateTracker tracker;

  public ChatController(ChatUseCase u, ChatRestMapper m, MessageStateTracker t) {
    useCase = u;
    mapper = m;
    tracker = t;
  }

  @PostMapping
  public ChatHttpResponse chat(@Valid @RequestBody ChatHttpRequest r) {
    return mapper.toResponse(useCase.execute(mapper.toApplication(r)));
  }

  @GetMapping("/{messageId}/status")
  public MessageStatusHttpResponse status(@PathVariable String messageId) {
    var s = tracker.current(messageId);
    if (s == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Message not found");
    return mapper.toStatus(messageId, s);
  }
}
