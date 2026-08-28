package com.ada.conversation.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.ada.conversation.application.dto.ChatRequest;
import com.ada.conversation.application.dto.ChatResult;
import com.ada.conversation.application.port.in.RequestFilter;
import com.ada.conversation.application.port.out.*;
import com.ada.conversation.manager.AdaInfoManager;
import com.ada.conversation.manager.MemoryManager;
import com.ada.conversation.manager.ToolManager;
import com.ada.shared.observability.AdaMetrics;
import java.util.List;
import java.util.function.Supplier;
import org.junit.jupiter.api.Test;

class ChatUseCaseTest {
  @Test
  void infoCommandIsStoredWithoutCallingModelFlow() {
    var selector = mock(SelectModelUseCase.class);
    var factory = mock(LlmRequestFactory.class);
    var client = mock(LlmClient.class);
    var metrics = mock(AdaMetrics.class);
    var toolManager = mock(ToolManager.class);
    var memoryManager = mock(MemoryManager.class);
    var infoManager = mock(AdaInfoManager.class);
    var tracker = mock(MessageStateTracker.class);
    var results = mock(MessageResultStore.class);
    when(infoManager.supports("/i")).thenReturn(true);
    when(infoManager.describe()).thenReturn("ADA info");
    when(metrics.startRequest()).thenReturn(1L);
    doAnswer(invocation -> ((Supplier<?>) invocation.getArgument(1)).get())
        .when(metrics)
        .measureStage(anyString(), any());

    var useCase =
        new ChatUseCase(
            selector,
            factory,
            client,
            metrics,
            List.<RequestFilter>of(),
            toolManager,
            memoryManager,
            infoManager,
            tracker,
            results,
            Runnable::run);

    ChatResult result = useCase.execute(new ChatRequest("/i", null));

    assertThat(result.content()).isEqualTo("ADA info");
    verify(results).save(any(ChatResult.class));
    verifyNoInteractions(selector, factory, client, toolManager, memoryManager);
  }
}
