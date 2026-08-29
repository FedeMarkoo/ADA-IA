package com.ada.conversation.infrastructure.in.rest;

import com.ada.conversation.infrastructure.in.rest.dto.RagDocumentCreatedHttpResponse;
import com.ada.conversation.infrastructure.in.rest.dto.RagDocumentHttpRequest;
import com.ada.conversation.manager.RagManager;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/rag/documents")
@RequiredArgsConstructor
public class RagController {
  private final RagManager ragManager;

  @PostMapping
  @ResponseStatus(HttpStatus.CREATED)
  public RagDocumentCreatedHttpResponse index(@Valid @RequestBody RagDocumentHttpRequest request) {
    return new RagDocumentCreatedHttpResponse(
        ragManager.index(request.conversationId(), request.source(), request.content()));
  }
}
