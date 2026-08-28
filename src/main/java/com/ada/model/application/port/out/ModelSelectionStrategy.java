package com.ada.model.application.port.out;

import com.ada.conversation.application.dto.*;
public interface ModelSelectionStrategy { boolean supports(ChatRequest request); ModelSelection select(ChatRequest request); }
