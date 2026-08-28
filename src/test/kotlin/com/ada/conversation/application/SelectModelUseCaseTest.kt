package com.ada.conversation.application

import com.ada.dto.ChatRequest
import com.ada.conversation.application.port.`in`.RequestFilter
import com.ada.dto.ModelSelection
import com.ada.model.application.port.out.ModelSelectionStrategy
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertSame
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Test

class SelectModelUseCaseTest {
    @Test
    fun `applies supported filters in order before using the first supported strategy`() {
        val filterInputs = mutableListOf<ChatRequest>()
        var selectedRequest: ChatRequest? = null
        val trimFilter = filter(
            apply = { request ->
                filterInputs += request
                request.copy(message = request.message.trim())
            },
        )
        val unsupportedFilter = filter(
            supports = { false },
            apply = { throw AssertionError("An unsupported filter must not be applied") },
        )
        val suffixFilter = filter(
            apply = { request ->
                filterInputs += request
                request.copy(message = "${request.message}!")
            },
        )
        val unsupportedStrategy = strategy(
            supports = { false },
            select = { throw AssertionError("An unsupported strategy must not select a model") },
        )
        val selectedStrategy = strategy(
            select = { request ->
                selectedRequest = request
                ModelSelection("local/model")
            },
        )
        val laterStrategy = strategy(
            supports = { throw AssertionError("Strategies after the first match must not be evaluated") },
        )
        val useCase = SelectModelUseCase(
            filters = listOf(trimFilter, unsupportedFilter, suffixFilter),
            strategies = listOf(unsupportedStrategy, selectedStrategy, laterStrategy),
        )

        val selection = useCase.execute(ChatRequest("  hello  ", requestedModel = "preferred/model"))

        assertEquals(ModelSelection("local/model"), selection)
        assertEquals(
            listOf(
                ChatRequest("  hello  ", requestedModel = "preferred/model"),
                ChatRequest("hello", requestedModel = "preferred/model"),
            ),
            filterInputs,
        )
        assertEquals(ChatRequest("hello!", requestedModel = "preferred/model"), selectedRequest)
    }

    @Test
    fun `passes the original request to a strategy when no filter is supported`() {
        val request = ChatRequest("unchanged")
        var receivedRequest: ChatRequest? = null
        val useCase = SelectModelUseCase(
            filters = listOf(
                filter(
                    supports = { false },
                    apply = { throw AssertionError("An unsupported filter must not be applied") },
                ),
            ),
            strategies = listOf(
                strategy(
                    select = {
                        receivedRequest = it
                        ModelSelection("fallback/model")
                    },
                ),
            ),
        )

        useCase.execute(request)

        assertSame(request, receivedRequest)
    }

    @Test
    fun `fails clearly when no strategy supports the filtered request`() {
        var selectCalls = 0
        val useCase = SelectModelUseCase(
            filters = listOf(filter(apply = { it.copy(message = it.message.trim()) })),
            strategies = listOf(
                strategy(
                    supports = { false },
                    select = {
                        selectCalls += 1
                        ModelSelection("must-not-be-selected")
                    },
                ),
            ),
        )

        val error = assertThrows(IllegalStateException::class.java) {
            useCase.execute(ChatRequest(" unsupported "))
        }

        assertEquals("No model selection strategy supports the request", error.message)
        assertEquals(0, selectCalls)
    }

    @Test
    fun `does not evaluate strategies when a filter fails`() {
        val filterFailure = IllegalArgumentException("invalid request")
        var strategySupportCalls = 0
        val useCase = SelectModelUseCase(
            filters = listOf(filter(apply = { throw filterFailure })),
            strategies = listOf(
                strategy(
                    supports = {
                        strategySupportCalls += 1
                        true
                    },
                ),
            ),
        )

        val thrown = assertThrows(IllegalArgumentException::class.java) {
            useCase.execute(ChatRequest("message"))
        }

        assertSame(filterFailure, thrown)
        assertEquals(0, strategySupportCalls)
    }

    private fun filter(
        supports: (ChatRequest) -> Boolean = { true },
        apply: (ChatRequest) -> ChatRequest,
    ): RequestFilter = object : RequestFilter {
        override fun supports(request: ChatRequest): Boolean = supports.invoke(request)

        override fun apply(request: ChatRequest): ChatRequest = apply.invoke(request)
    }

    private fun strategy(
        supports: (ChatRequest) -> Boolean = { true },
        select: (ChatRequest) -> ModelSelection = { ModelSelection("model") },
    ): ModelSelectionStrategy = object : ModelSelectionStrategy {
        override fun supports(request: ChatRequest): Boolean = supports.invoke(request)

        override fun select(request: ChatRequest): ModelSelection = select.invoke(request)
    }
}
