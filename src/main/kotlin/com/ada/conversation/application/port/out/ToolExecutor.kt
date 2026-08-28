package com.ada.conversation.application.port.out

import com.ada.conversation.application.dto.LlmToolCall
import com.ada.conversation.application.dto.ToolExecutionResult

interface ToolExecutor {
    fun supports(toolName: String): Boolean

    fun execute(call: LlmToolCall): ToolExecutionResult
}
