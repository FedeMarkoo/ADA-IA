package com.ada.conversation.application

import com.ada.conversation.application.port.`in`.ChatRequest
import com.ada.conversation.application.port.out.LlmClient
import com.ada.conversation.application.port.out.LlmContentComponent
import com.ada.conversation.application.port.out.LlmMessage
import com.ada.conversation.application.port.out.LlmMessageRole
import com.ada.conversation.application.port.out.LlmRequest
import com.ada.conversation.application.port.out.LlmRequestMetadata
import com.ada.conversation.application.port.out.LlmTool
import com.ada.shared.observability.AdaMetrics
import org.springframework.stereotype.Service
import java.util.UUID

data class ChatResult(
    val content: String,
    val model: String,
    val inputTokens: Long? = null,
    val outputTokens: Long? = null,
)

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
        val completion = metrics.measureLlm(llmRequest.model) {
            llmClient.complete(llmRequest)
        }

        metrics.recordRequest("conversation", "chat", "success")
        metrics.recordTokenBreakdown(llmRequest, completion)
        return ChatResult(
            content = completion.content,
            model = completion.model,
            inputTokens = completion.inputTokens,
            outputTokens = completion.outputTokens,
        )
    }
}

@Service
class LlmRequestFactory(
    private val systemPromptProvider: SystemPromptProvider,
    private val toolProviders: List<ToolProvider>,
) {
    fun create(request: ChatRequest, model: String): LlmRequest {
        val tools = toolProviders.flatMap { provider -> provider.tools() }
        return LlmRequest(
            model = model,
            messages = listOf(
                LlmMessage(
                    role = LlmMessageRole.SYSTEM,
                    content = systemPromptProvider.content(),
                    component = LlmContentComponent.SYSTEM,
                ),
                LlmMessage(
                    role = LlmMessageRole.USER,
                    content = request.message,
                    component = LlmContentComponent.PROMPT,
                ),
            ),
            tools = tools,
            metadata = LlmRequestMetadata(correlationId = UUID.randomUUID().toString()),
        )
    }
}

interface SystemPromptProvider {
    fun content(): String
}

interface ToolProvider {
    fun tools(): List<LlmTool>
}
