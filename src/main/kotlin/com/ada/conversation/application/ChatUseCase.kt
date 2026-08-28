package com.ada.conversation.application

import com.ada.conversation.application.port.`in`.ChatRequest
import com.ada.conversation.application.port.out.LlmClient
import com.ada.model.application.port.out.ModelSelectionStrategy
import com.ada.shared.observability.AdaMetrics
import org.springframework.stereotype.Service

data class ChatResult(
    val content: String,
    val model: String,
    val inputTokens: Long? = null,
    val outputTokens: Long? = null,
)

@Service
class ChatUseCase(
    private val selectModelUseCase: SelectModelUseCase,
    private val llmClient: LlmClient,
    private val metrics: AdaMetrics,
) {
    fun execute(request: ChatRequest): ChatResult {
        val selection = selectModelUseCase.execute(request)
        val completion = metrics.measureLlm(selection.model) {
            llmClient.complete(request, selection.model)
        }

        metrics.recordRequest("conversation", "chat", "success")
        return ChatResult(
            content = completion.content,
            model = completion.model,
            inputTokens = completion.inputTokens,
            outputTokens = completion.outputTokens,
        )
    }
}
