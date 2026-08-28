package com.ada.shared.infrastructure;

import java.nio.file.*;
import java.util.*;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.*;

@Configuration
@RequiredArgsConstructor
public class DataDirectoryInitializer {
  private final AdaProperties properties;

  @Bean
  public ApplicationRunner initializeDataDirectory() {
    return args -> {
      for (String d : List.of("db", "logs", "backups", "exports", "models", "runtime"))
        Files.createDirectories(properties.getNormalizedDataDirectory().resolve(d));
    };
  }
}
