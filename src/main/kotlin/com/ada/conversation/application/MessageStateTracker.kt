package com.ada.conversation.application

import com.ada.conversation.application.dto.MessageExecutionState

interface MessageStateTracker {
    fun update(messageId: String, state: MessageExecutionState)

    fun current(messageId: String): MessageExecutionState?
}
