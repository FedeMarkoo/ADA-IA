package com.ada.conversation.application

import com.ada.conversation.application.port.out.LlmClient
import com.ada.conversation.application.port.out.ToolExecutor
import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ChatResult
import com.ada.conversation.application.dto.LlmContentComponent
import com.ada.conversation.application.dto.LlmMessage
import com.ada.conversation.application.dto.LlmMessageRole
import com.ada.conversation.application.dto.LlmRequest
import com.ada.conversation.application.dto.LlmCompletion
import com.ada.conversation.application.dto.ToolExecutionResult
import com.ada.conversation.application.dto.MessageExecutionState
import com.ada.conversation.application.port.`in`.RequestFilter
import com.ada.shared.observability.AdaMetrics
import org.springframework.stereotype.Service
import java.util.UUID

@Service
class ChatUseCase(
    private val selectModelUseCase: SelectModelUseCase,
    private val llmRequestFactory: LlmRequestFactory,
    private val llmClient: LlmClient,
    private val metrics: AdaMetrics,
    private val requestFilters: List<RequestFilter>,
    private val toolExecutors: List<ToolExecutor>,
    private val messageStateTracker: MessageStateTracker,
) {
    fun execute(request: ChatRequest): ChatResult {
        val messageId = UUID.randomUUID().toString()
        messageStateTracker.update(messageId, MessageExecutionState.Received)
        return try {
            val filteredRequest = applyFilters(messageId, request)
            val selection = selectModelUseCase.execute(filteredRequest)
            messageStateTracker.update(messageId, MessageExecutionState.CreatingContext)
            var llmRequest = llmRequestFactory.create(filteredRequest, selection.model)
            var completion = invokeModel(messageId, llmRequest)
            var rounds = 0

            while (completion.toolCalls.isNotEmpty()) {
                check(rounds++ < MAX_TOOL_ROUNDS) { "Maximum tool rounds exceeded" }
                val toolResults = completion.toolCalls.map { call ->
                    messageStateTracker.update(messageId, MessageExecutionState.InvokingTool(call.name))
                    val executor = toolExecutors.firstOrNull { it.supports(call.name) }
                        ?: error("No executor available for tool '${call.name}'")
                    executor.execute(call)
                }
                llmRequest = appendToolResults(llmRequest, completion, toolResults)
                completion = invokeModel(messageId, llmRequest)
            }

            messageStateTracker.update(messageId, MessageExecutionState.Completed)
            metrics.recordRequest("conversation", "chat", "success")
            ChatResult(messageId, completion.content, completion.model, completion.inputTokens, completion.outputTokens)
        } catch (error: RuntimeException) {
            messageStateTracker.update(messageId, MessageExecutionState.Failed(error.message ?: "unknown error"))
            throw error
        }
    }

    private fun applyFilters(messageId: String, request: ChatRequest): ChatRequest {
        messageStateTracker.update(messageId, MessageExecutionState.FilteringCommand)
        return requestFilters.sortedWith(org.springframework.core.annotation.AnnotationAwareOrderComparator.INSTANCE)
            .fold(request) { current, filter ->
                if (filter.supports(current)) filter.apply(current) else current
            }
    }

    private fun invokeModel(messageId: String, request: LlmRequest): LlmCompletion =
        run {
            messageStateTracker.update(messageId, MessageExecutionState.InvokingModel(request.model))
            val completion = metrics.measureLlm(request.model) { llmClient.complete(request) }
            metrics.recordTokenBreakdown(request, completion)
            completion
        }

    private fun appendToolResults(
        request: LlmRequest,
        completion: LlmCompletion,
        results: List<ToolExecutionResult>,
    ): LlmRequest = request.copy(
        messages = request.messages +
            LlmMessage(
                LlmMessageRole.ASSISTANT,
                completion.content,
                LlmContentComponent.RESPONSE,
                completion.toolCalls,
            ) +
            results.map { LlmMessage(LlmMessageRole.TOOL, it.content, LlmContentComponent.TOOL_RESPONSE) },
    )

    private companion object {
        const val MAX_TOOL_ROUNDS = 8
    }
}
