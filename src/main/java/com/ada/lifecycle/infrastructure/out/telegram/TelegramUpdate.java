package com.ada.lifecycle.infrastructure.out.telegram;

public record TelegramUpdate(long updateId, String chatId, String text) {}
