package com.ada.lifecycle.infrastructure.out.telegram.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public record TelegramMessage(@JsonProperty("chat_id") String chatId, String text) {}
