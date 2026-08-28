package com.ada;

import static org.junit.jupiter.api.Assertions.assertTrue;

import com.ada.shared.infrastructure.AdaProperties;
import com.ada.shared.infrastructure.DataSourceConfiguration;
import com.ada.shared.infrastructure.dto.LlmProperties;
import java.nio.file.Files;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class DataSourceConfigurationTest {
  @TempDir java.nio.file.Path tempDir;

  @Test
  void createsDatabaseDirectoryWhenParentDoesNotExist() throws Exception {
    var dataDir = tempDir.resolve("missing-parent");
    var properties =
        new AdaProperties(dataDir.toString(), new LlmProperties("http://localhost", "", "model"));

    var dataSource = new DataSourceConfiguration().dataSource(properties);
    try (var connection = dataSource.getConnection()) {
      assertTrue(Files.exists(dataDir.resolve("db/ada.sqlite")));
      assertTrue(connection.isValid(1));
    }
  }
}
