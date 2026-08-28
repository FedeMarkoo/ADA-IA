package com.ada.shared.infrastructure

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import org.springframework.boot.DefaultApplicationArguments
import java.nio.file.FileAlreadyExistsException
import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.readText
import kotlin.io.path.writeText

class DataDirectoryInitializerTest {
    @Test
    fun `creates the complete data directory layout`(@TempDir temporaryDirectory: Path) {
        val dataDirectory = temporaryDirectory.resolve("nested/data directory")

        runInitializer(dataDirectory)

        val createdDirectories = Files.list(dataDirectory).use { paths ->
            paths.map { it.fileName.toString() }.toList().toSet()
        }
        assertEquals(EXPECTED_DIRECTORIES, createdDirectories)
        EXPECTED_DIRECTORIES.forEach { name ->
            assertTrue(
                Files.isDirectory(dataDirectory.resolve(name)),
                "Expected $name to be created as a directory",
            )
        }
    }

    @Test
    fun `can run repeatedly without replacing existing data`(@TempDir temporaryDirectory: Path) {
        val dataDirectory = temporaryDirectory.resolve("ada-data")
        runInitializer(dataDirectory)
        val existingDatabase = dataDirectory.resolve("db/ada.sqlite")
        existingDatabase.writeText("existing data")

        runInitializer(dataDirectory)

        assertEquals("existing data", existingDatabase.readText())
    }

    @Test
    fun `fails when a required directory path is already a file`(@TempDir temporaryDirectory: Path) {
        val dataDirectory = temporaryDirectory.resolve("ada-data")
        Files.createDirectories(dataDirectory)
        Files.createFile(dataDirectory.resolve("logs"))

        assertThrows(FileAlreadyExistsException::class.java) {
            runInitializer(dataDirectory)
        }
    }

    private fun runInitializer(dataDirectory: Path) {
        DataDirectoryInitializer(dataDirectory.toString())
            .initializeDataDirectory()
            .run(DefaultApplicationArguments())
    }

    private companion object {
        val EXPECTED_DIRECTORIES = setOf("db", "logs", "backups", "exports", "models", "runtime")
    }
}
