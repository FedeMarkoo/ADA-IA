package com.ada.conversation.manager;

import com.ada.conversation.application.dto.ChatRequest;
import com.ada.conversation.application.dto.MemoryCandidate;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.regex.Pattern;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class MemoryManager {
  private static final Pattern EXPLICIT_MEMORY =
      Pattern.compile(
          "\\b(record[aá]|acord[aá]|remember|remember that|mi nombre es|prefiero|me gusta)\\b",
          Pattern.CASE_INSENSITIVE);

  private final List<MemoryCandidate> memories = new CopyOnWriteArrayList<>();

  public List<String> relevantMemories(ChatRequest request) {
    var query = request.message().toLowerCase(Locale.ROOT);
    return memories.stream()
        .filter(memory -> sharesMeaningfulWord(memory.subject(), query))
        .map(MemoryCandidate::content)
        .toList();
  }

  public MemoryCandidate review(ChatRequest request, String response) {
    if (!isExplicitlyUseful(request.message())) return null;
    var candidate = new MemoryCandidate(request.message(), response);
    memories.removeIf(item -> item.subject().equalsIgnoreCase(candidate.subject()));
    memories.add(candidate);
    return candidate;
  }

  private boolean isExplicitlyUseful(String prompt) {
    return EXPLICIT_MEMORY.matcher(prompt).find();
  }

  private boolean sharesMeaningfulWord(String subject, String query) {
    return List.of(subject.toLowerCase(Locale.ROOT).split("\\W+")).stream()
        .filter(word -> word.length() >= 5)
        .anyMatch(query::contains);
  }
}
