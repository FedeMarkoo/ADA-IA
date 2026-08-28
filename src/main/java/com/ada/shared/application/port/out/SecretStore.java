package com.ada.shared.application.port.out;

import java.util.Optional;

public interface SecretStore {
  Optional<String> find(String name);

  void saveIfAbsent(String name, String value);
}
