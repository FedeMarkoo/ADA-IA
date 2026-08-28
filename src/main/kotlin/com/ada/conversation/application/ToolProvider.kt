package com.ada.conversation.application

import com.ada.dto.LlmTool

interface ToolProvider { fun tools(): List<LlmTool> }
