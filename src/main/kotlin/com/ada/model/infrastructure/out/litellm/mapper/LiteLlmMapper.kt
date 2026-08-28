package com.ada.model.infrastructure.out.litellm.mapper

import com.ada.conversation.application.dto.LlmMessage
import com.ada.conversation.application.dto.LlmRequest
import com.ada.conversation.application.dto.LlmTool
import com.ada.model.infrastructure.out.litellm.dto.LiteLlmFunctionCall
import com.ada.model.infrastructure.out.litellm.dto.LiteLlmMessage
import com.ada.model.infrastructure.out.litellm.dto.LiteLlmRequest
import com.ada.model.infrastructure.out.litellm.dto.LiteLlmToolCall
import com.ada.model.infrastructure.out.litellm.dto.LiteLlmTool
import org.mapstruct.Mapper

@Mapper(componentModel = "spring")
abstract class LiteLlmMapper {
    abstract fun toRequest(request: LlmRequest): LiteLlmRequest

    protected fun toMessage(message: LlmMessage): LiteLlmMessage = LiteLlmMessage(
        role = message.role.wireName(),
        content = message.content,
        toolCalls = message.toolCalls.map(::toToolCall),
    )

    protected fun toToolCall(call: com.ada.conversation.application.dto.LlmToolCall): LiteLlmToolCall =
        LiteLlmToolCall(call.id, function = LiteLlmFunctionCall(call.name, call.arguments))

    protected fun toTool(tool: LlmTool): LiteLlmTool = LiteLlmTool(
        name = tool.name,
        description = tool.description,
        inputSchema = tool.inputSchema,
    )
}
