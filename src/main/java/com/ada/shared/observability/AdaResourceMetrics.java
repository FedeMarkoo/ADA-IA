package com.ada.shared.observability;

import com.sun.management.OperatingSystemMXBean;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tags;
import jakarta.annotation.PostConstruct;
import java.io.IOException;
import java.lang.management.ManagementFactory;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class AdaResourceMetrics {
  private static final Pattern RSS_PATTERN = Pattern.compile("VmRSS:\\s+(\\d+)\\s+kB");
  private static final Pattern MODEL_PATTERN =
      Pattern.compile("\\\"name\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"");
  private static final String[] COMPONENTS = {"ada", "ollama", "telegram", "prometheus", "grafana"};

  private final MeterRegistry registry;
  private final OperatingSystemMXBean operatingSystem =
      (OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean();
  private final Map<String, Double> componentMemory = new ConcurrentHashMap<>();
  private final Map<String, Double> modelMemory = new ConcurrentHashMap<>();
  private final Set<String> registeredModels = ConcurrentHashMap.newKeySet();
  private final HttpClient httpClient = HttpClient.newBuilder().build();

  @PostConstruct
  void initialize() {
    registerMemoryGauges();
    refreshProcessMetrics();
  }

  @Scheduled(fixedDelayString = "${ada.metrics.resource-refresh-ms:5000}")
  void refreshProcessMetrics() {
    var snapshot = scanProcesses();
    componentMemory.clear();
    componentMemory.putAll(snapshot);
    for (var component : COMPONENTS) componentMemory.putIfAbsent(component, 0.0);
    refreshModelMemory(snapshot.getOrDefault("ollama", 0.0));
  }

  private void registerMemoryGauges() {
    register("total", OperatingSystemMXBean::getTotalMemorySize);
    register("free", OperatingSystemMXBean::getFreeMemorySize);
    register("used", bean -> bean.getTotalMemorySize() - bean.getFreeMemorySize());
    registry.gauge(
        "ada_process_memory_bytes",
        Tags.of("state", "rss"),
        this,
        item -> item.componentMemory.getOrDefault("ada", 0.0));
    for (var component : COMPONENTS) {
      registry.gauge(
          "ada_component_memory_bytes",
          Tags.of("component", component),
          this,
          item -> item.componentMemory.getOrDefault(component, 0.0));
    }
  }

  private void register(
      String state, java.util.function.ToDoubleFunction<OperatingSystemMXBean> value) {
    registry.gauge(
        "ada_system_memory_bytes",
        io.micrometer.core.instrument.Tags.of("state", state),
        operatingSystem,
        value);
  }

  private Map<String, Double> scanProcesses() {
    var result = new ConcurrentHashMap<String, Double>();
    try (var processes = Files.list(Path.of("/proc"))) {
      processes
          .filter(path -> path.getFileName().toString().matches("\\d+"))
          .forEach(path -> addProcess(result, path));
    } catch (IOException ignored) {
      // Resource metrics are best effort and must never affect application traffic.
    }
    return result;
  }

  private void addProcess(Map<String, Double> result, Path processPath) {
    try {
      var command =
          Files.readString(processPath.resolve("cmdline")).replace('\0', ' ').toLowerCase();
      var name = Files.readString(processPath.resolve("comm")).trim().toLowerCase();
      var component = componentOf(name, command);
      if (component != null) result.merge(component, residentBytes(processPath), Double::sum);
    } catch (IOException | NumberFormatException ignored) {
      // Processes can disappear while /proc is being read.
    }
  }

  private String componentOf(String name, String command) {
    if (command.contains("ada-0.1.0-snapshot.jar")) return "ada";
    if (name.equals("ollama") || name.equals("llama-server")) return "ollama";
    if (command.contains("telegram/bot") || command.contains("telegram.bot")) return "telegram";
    if (name.startsWith("prometheus")) return "prometheus";
    if (name.startsWith("grafana")) return "grafana";
    return null;
  }

  private double residentBytes(Path processPath) throws IOException {
    var matcher = RSS_PATTERN.matcher(Files.readString(processPath.resolve("status")));
    return matcher.find() ? Long.parseLong(matcher.group(1)) * 1024.0 : 0.0;
  }

  private void refreshModelMemory(double ollamaMemory) {
    var models = loadedModels();
    if (models.isEmpty()) models = java.util.List.of("unknown");
    var memoryPerModel = ollamaMemory / models.size();
    modelMemory.replaceAll((model, value) -> 0.0);
    for (var model : models) {
      modelMemory.put(model, memoryPerModel);
      if (registeredModels.add(model)) {
        registry.gauge(
            "ada_ollama_model_memory_bytes",
            Tags.of("model", model),
            this,
            item -> item.modelMemory.getOrDefault(model, 0.0));
      }
    }
  }

  private java.util.List<String> loadedModels() {
    try {
      var request =
          HttpRequest.newBuilder(URI.create("http://127.0.0.1:11434/api/ps")).GET().build();
      var response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
      if (response.statusCode() != 200) return java.util.List.of();
      var matcher = MODEL_PATTERN.matcher(response.body());
      var models = new java.util.ArrayList<String>();
      while (matcher.find()) models.add(matcher.group(1));
      return models.stream().distinct().collect(Collectors.toList());
    } catch (InterruptedException e) {
      Thread.currentThread().interrupt();
      return java.util.List.of();
    } catch (IOException | RuntimeException e) {
      return java.util.List.of();
    }
  }
}
