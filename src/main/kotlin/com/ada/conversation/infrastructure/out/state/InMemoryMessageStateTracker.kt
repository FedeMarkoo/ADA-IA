package com.ada.conversation.infrastructure.out.state

import com.ada.conversation.application.MessageStateTracker
import com.ada.conversation.application.dto.MessageExecutionState
import org.springframework.stereotype.Component
import java.util.concurrent.ConcurrentHashMap

@Component
class InMemoryMessageStateTracker : MessageStateTracker {
    private val states = ConcurrentHashMap<String, MessageExecutionState>()

    override fun update(messageId: String, state: MessageExecutionState) {
        states[messageId] = state
    }

    override fun current(messageId: String): MessageExecutionState? = states[messageId]
}
