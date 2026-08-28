package com.ada.shared.infrastructure.out.secrets;

import com.ada.shared.application.port.out.SecretStore;
import com.ada.shared.infrastructure.AdaProperties;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.Optional;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class EncryptedSecretStore implements SecretStore {
  private static final String CIPHER = "AES/GCM/NoPadding";
  private static final int NONCE_SIZE = 12;
  private static final int TAG_SIZE_BITS = 128;

  private final JdbcTemplate jdbc;
  private final AdaProperties properties;
  private final SecureRandom random = new SecureRandom();

  @Override
  public Optional<String> find(String name) {
    var values =
        jdbc.query(
            "SELECT value FROM ada_secrets WHERE name = ?", (rs, row) -> rs.getBytes(1), name);
    return values.stream().findFirst().map(this::decrypt);
  }

  @Override
  public void saveIfAbsent(String name, String value) {
    if (value == null || value.isBlank() || find(name).isPresent()) return;
    jdbc.update("INSERT INTO ada_secrets(name, value) VALUES (?, ?)", name, encrypt(value));
  }

  private byte[] encrypt(String value) {
    try {
      byte[] nonce = new byte[NONCE_SIZE];
      random.nextBytes(nonce);
      var cipher = Cipher.getInstance(CIPHER);
      cipher.init(Cipher.ENCRYPT_MODE, key(), new GCMParameterSpec(TAG_SIZE_BITS, nonce));
      byte[] plaintext = value.getBytes(StandardCharsets.UTF_8);
      return ByteBuffer.allocate(nonce.length + cipher.getOutputSize(plaintext.length))
          .put(nonce)
          .put(cipher.doFinal(plaintext))
          .array();
    } catch (GeneralSecurityException exception) {
      throw new IllegalStateException("Could not encrypt a secret", exception);
    }
  }

  private String decrypt(byte[] encrypted) {
    try {
      var buffer = ByteBuffer.wrap(encrypted);
      byte[] nonce = new byte[NONCE_SIZE];
      buffer.get(nonce);
      var cipher = Cipher.getInstance(CIPHER);
      cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(TAG_SIZE_BITS, nonce));
      return new String(
          cipher.doFinal(buffer.array(), buffer.position(), buffer.remaining()),
          StandardCharsets.UTF_8);
    } catch (GeneralSecurityException | RuntimeException exception) {
      throw new IllegalStateException("Could not decrypt a secret", exception);
    }
  }

  private SecretKeySpec key() {
    var encoded = properties.getSecrets() == null ? null : properties.getSecrets().getMasterKey();
    if (encoded == null || encoded.isBlank())
      throw new IllegalStateException("ADA_SECRET_MASTER_KEY is required to use encrypted secrets");
    try {
      byte[] key = Base64.getDecoder().decode(encoded);
      if (key.length != 32) throw new IllegalArgumentException("master key must be 32 bytes");
      return new SecretKeySpec(key, "AES");
    } catch (IllegalArgumentException exception) {
      throw new IllegalStateException(
          "ADA_SECRET_MASTER_KEY must be base64-encoded 32 bytes", exception);
    }
  }
}
