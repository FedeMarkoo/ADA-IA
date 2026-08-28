package com.ada.conversation.infrastructure.in.rest;

import com.ada.conversation.application.ChatUseCase;
import com.ada.conversation.application.port.out.MessageResultStore;
import com.ada.conversation.application.port.out.MessageStateTracker;
import com.ada.conversation.infrastructure.in.rest.dto.*;
import com.ada.conversation.infrastructure.in.rest.mapper.ChatRestMapper;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
@RequestMapping("/api/v1/chat")
@RequiredArgsConstructor
public class ChatController {
  private final ChatUseCase useCase;
  private final ChatRestMapper mapper;
  private final MessageStateTracker tracker;
  private final MessageResultStore results;

  @PostMapping
  public ResponseEntity<ChatAcceptedHttpResponse> chat(@Valid @RequestBody ChatHttpRequest r) {
    return ResponseEntity.accepted()
        .body(new ChatAcceptedHttpResponse(useCase.start(mapper.toApplication(r))));
  }

  @GetMapping("/{messageId}/status")
  public MessageStatusHttpResponse status(@PathVariable String messageId) {
    var s = tracker.current(messageId);
    if (s == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Message not found");
    return mapper.toStatus(messageId, s);
  }

  @GetMapping(value = "/{messageId}/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
  public SseEmitter events(@PathVariable String messageId) {
    var current = tracker.current(messageId);
    if (current == null) {
      throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Message not found");
    }

    var emitter = new SseEmitter(300_000L);
    var subscription = tracker.subscribe(messageId, state -> sendState(emitter, messageId, state));
    if (subscription == null) {
      emitter.completeWithError(
          new ResponseStatusException(HttpStatus.NOT_FOUND, "Message not found"));
      return emitter;
    }
    emitter.onCompletion(subscription::close);
    emitter.onTimeout(
        () -> {
          subscription.close();
          emitter.complete();
        });
    emitter.onError(ignored -> subscription.close());
    sendState(emitter, messageId, current);
    return emitter;
  }

  @GetMapping("/{messageId}")
  public ChatHttpResponse result(@PathVariable String messageId) {
    var result = results.find(messageId);
    if (result == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Result not found");
    return mapper.toResponse(result);
  }

  private void sendState(
      SseEmitter emitter,
      String messageId,
      com.ada.conversation.application.dto.MessageExecutionState state) {
    try {
      emitter.send(SseEmitter.event().name("status").data(mapper.toStatus(messageId, state)));
      if (isTerminal(state)) emitter.complete();
    } catch (Exception exception) {
      emitter.completeWithError(exception);
    }
  }

  private boolean isTerminal(com.ada.conversation.application.dto.MessageExecutionState state) {
    return state instanceof com.ada.conversation.application.dto.MessageExecutionState.Completed
        || state instanceof com.ada.conversation.application.dto.MessageExecutionState.Failed;
  }
}
