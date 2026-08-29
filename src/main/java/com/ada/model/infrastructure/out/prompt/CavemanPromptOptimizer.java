package com.ada.model.infrastructure.out.prompt;

import com.ada.conversation.application.dto.LlmContentComponent;
import com.ada.conversation.application.dto.LlmMessage;
import com.ada.conversation.application.dto.LlmMessageRole;
import com.ada.conversation.application.dto.LlmRequest;
import com.ada.conversation.application.port.out.PromptOptimizer;
import java.util.regex.Pattern;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/** Conservative, local prompt compaction inspired by Caveman Compression. */
@Component
public class CavemanPromptOptimizer implements PromptOptimizer {
  private static final Pattern MULTIPLE_SPACES = Pattern.compile("[ \\t]{2,}");
  private static final Pattern MULTIPLE_BLANK_LINES = Pattern.compile("\\n{3,}");
  private static final Pattern FILLER =
      Pattern.compile(
          "(?iu)(?<!\\p{L})(?:por favor,? ten en cuenta que|ten en cuenta que|es importante que|a continuación|a continuacion|simplemente|básicamente|basicamente|en general|please|simply|basically|in general|note that)(?!\\p{L})[,:]?\\s*");
  private static final Pattern CODE_OR_DATA =
      Pattern.compile(
          "(?ims)(?:^|\\n)\\s*(?:select|insert|update|delete|create|alter|drop|with|def|class|import|from|return|if|for|while|#!/|bash\\b|sh\\b|python\\b|npm\\b|mvn\\b|curl\\b)|(?:=>|\\b(public|private|static|void|function)\\b)|^\\s*\\\"[^\\\"]+\\\"\\s*$|;\\s*$|<\\/?[A-Za-z][^>]*>|\\\\\"|\\b[A-Za-z_][A-Za-z0-9_]*\\s*=\\s*[^=]");

  private final boolean enabled;
  private final int minimumCharacters;

  public CavemanPromptOptimizer(
      @Value("${ada.llm.prompt-optimization.enabled:true}") boolean enabled,
      @Value("${ada.llm.prompt-optimization.min-chars:120}") int minimumCharacters) {
    if (minimumCharacters < 0) {
      throw new IllegalArgumentException("Prompt optimization min-chars must be non-negative");
    }
    this.enabled = enabled;
    this.minimumCharacters = minimumCharacters;
  }

  @Override
  public LlmRequest optimize(LlmRequest request) {
    if (!enabled) return request;
    var messages = request.messages().stream().map(this::optimizeMessage).toList();
    if (messages.equals(request.messages())) return request;
    return new LlmRequest(
        request.model(),
        messages,
        request.tools(),
        request.temperature(),
        request.maxTokens(),
        request.metadata());
  }

  private LlmMessage optimizeMessage(LlmMessage message) {
    if (!isCompressible(message) || message.content() == null) return message;
    var content = message.content();
    if (content.length() < minimumCharacters || containsStructuredBlock(content)) return message;
    var optimized = compact(content);
    return optimized.equals(content)
        ? message
        : new LlmMessage(
            message.role(),
            optimized,
            message.component(),
            message.toolCalls(),
            message.toolCallId());
  }

  private boolean isCompressible(LlmMessage message) {
    return message.role() == LlmMessageRole.SYSTEM
        && (message.component() == LlmContentComponent.MEMORIES
            || message.component() == LlmContentComponent.COMPACTED_PROMPT);
  }

  private boolean containsStructuredBlock(String content) {
    return content.contains("```")
        || content.contains("{")
        || content.contains("[")
        || CODE_OR_DATA.matcher(content).find();
  }

  private String compact(String content) {
    var normalized = content.replace("\r\n", "\n").replace('\r', '\n');
    normalized = MULTIPLE_SPACES.matcher(normalized).replaceAll(" ");
    normalized = MULTIPLE_BLANK_LINES.matcher(normalized).replaceAll("\n\n");
    normalized = FILLER.matcher(normalized).replaceAll("");
    return normalized
        .lines()
        .map(String::stripTrailing)
        .filter(line -> !line.isBlank())
        .reduce((left, right) -> left + "\n" + right)
        .orElse("")
        .trim();
  }
}
