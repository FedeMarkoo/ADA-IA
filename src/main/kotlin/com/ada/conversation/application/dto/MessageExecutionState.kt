package com.ada.conversation.application.dto

sealed interface MessageExecutionState {
    val code: String
    val detail: String?

    data object Received : MessageExecutionState {
        override val code = "received"
        override val detail: String? = null
    }

    data object FilteringCommand : MessageExecutionState {
        override val code = "filtering_command"
        override val detail: String? = null
    }

    data object CreatingContext : MessageExecutionState {
        override val code = "creating_context"
        override val detail: String? = null
    }

    data class InvokingModel(val model: String) : MessageExecutionState {
        override val code = "invoking_model"
        override val detail = model
    }

    data class InvokingTool(val tool: String) : MessageExecutionState {
        override val code = "invoking_tool"
        override val detail = tool
    }

    data object Completed : MessageExecutionState {
        override val code = "completed"
        override val detail: String? = null
    }

    data class Failed(val reason: String) : MessageExecutionState {
        override val code = "failed"
        override val detail = reason
    }
}
