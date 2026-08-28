package com.ada.model.infrastructure.out.litellm.mapper;

import com.ada.conversation.application.dto.*; import com.ada.model.infrastructure.out.litellm.dto.*; import org.mapstruct.*;
@Mapper(componentModel="spring") public abstract class LiteLlmMapper { public LiteLlmRequest toRequest(LlmRequest r){return new LiteLlmRequest(r.model(),r.messages().stream().map(this::toMessage).toList(),r.tools().stream().map(t->new LiteLlmTool(t.name(),t.description(),t.inputSchema())).toList(),r.temperature(),r.maxTokens());} private LiteLlmMessage toMessage(LlmMessage m){return new LiteLlmMessage(m.role().wireName(),m.content(),m.toolCalls().stream().map(c->new LiteLlmToolCall(c.id(),new LiteLlmFunctionCall(c.name(),c.arguments()))).toList());} }
