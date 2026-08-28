package com.ada.conversation.application

import com.ada.conversation.application.port.out.LlmClient
import com.ada.conversation.application.dto.ChatRequest
import com.ada.conversation.application.dto.ChatResult
import com.ada.shared.observability.AdaMetrics
import org.springframework.stereotype.Service

@Service
class ChatUseCase(
    private val selectModelUseCase: SelectModelUseCase,
    private val llmRequestFactory: LlmRequestFactory,
    private val llmClient: LlmClient,
    private val metrics: AdaMetrics,
) {
    fun execute(request: ChatRequest): ChatResult {
        val selection = selectModelUseCase.execute(request)
        val llmRequest = llmRequestFactory.create(request, selection.model)
        val completion = metrics.measureLlm(llmRequest.model) { llmClient.complete(llmRequest) }
        metrics.recordRequest("conversation", "chat", "success")
        metrics.recordTokenBreakdown(llmRequest, completion)
        return ChatResult(completion.content, completion.model, completion.inputTokens, completion.outputTokens)
    }
}
