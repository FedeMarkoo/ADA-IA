package com.ada.conversation.application.dto;

public enum LlmMessageRole { SYSTEM,USER,ASSISTANT,TOOL; public String wireName(){return name().toLowerCase();} }
