package com.ada;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;

import com.ada.conversation.infrastructure.out.prompt.SystemPromptInitializer;
import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.infrastructure.DataDirectoryInitializer;
import java.nio.file.Files;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.boot.DefaultApplicationArguments;

class DataDirectoryInitializerTest {
  @TempDir java.nio.file.Path tempDir;

  @Test
  void createsLogsDirectoryAlongsideDatabaseDirectories() throws Exception {
    var properties = new AdaProperties();
    properties.setDataDir(tempDir.resolve("ada-data").toString());

    new DataDirectoryInitializer(properties, mock(SystemPromptInitializer.class))
        .initializeDataDirectory()
        .run(new DefaultApplicationArguments());

    assertTrue(Files.isDirectory(tempDir.resolve("ada-data/logs")));
    assertTrue(Files.isDirectory(tempDir.resolve("ada-data/db")));
  }
}
