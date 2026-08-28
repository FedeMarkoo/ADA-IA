package com.ada.conversation.application;

import com.ada.conversation.application.dto.*; import com.ada.conversation.context.ContextAssembler; import java.util.UUID; import org.springframework.stereotype.Service;
@Service public class LlmRequestFactory { private final ContextAssembler assembler; public LlmRequestFactory(ContextAssembler a){assembler=a;} public LlmRequest create(ChatRequest r,String model){var c=assembler.build(r);return new LlmRequest(model,c.messages(),c.tools(),new LlmRequestMetadata(UUID.randomUUID().toString()));} }
