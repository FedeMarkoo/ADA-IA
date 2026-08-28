package com.ada.shared.observability;

import com.sun.management.OperatingSystemMXBean;
import io.micrometer.core.instrument.MeterRegistry;
import java.io.IOException;
import java.lang.management.ManagementFactory;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Pattern;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class AdaResourceMetrics {
  private static final Pattern RSS_PATTERN = Pattern.compile("VmRSS:\\s+(\\d+)\\s+kB");

  private final MeterRegistry registry;
  private final OperatingSystemMXBean operatingSystem =
      (OperatingSystemMXBean) ManagementFactory.getOperatingSystemMXBean();

  @jakarta.annotation.PostConstruct
  void initialize() {
    registerMemoryGauges();
  }

  private void registerMemoryGauges() {
    register("total", OperatingSystemMXBean::getTotalMemorySize);
    register("free", OperatingSystemMXBean::getFreeMemorySize);
    register("used", bean -> bean.getTotalMemorySize() - bean.getFreeMemorySize());
    registry.gauge(
        "ada_process_memory_bytes",
        io.micrometer.core.instrument.Tags.of("state", "rss"),
        this,
        AdaResourceMetrics::processResidentBytes);
  }

  private void register(
      String state, java.util.function.ToDoubleFunction<OperatingSystemMXBean> value) {
    registry.gauge(
        "ada_system_memory_bytes",
        io.micrometer.core.instrument.Tags.of("state", state),
        operatingSystem,
        value);
  }

  private double processResidentBytes() {
    try {
      var status = Files.readString(Path.of("/proc/self/status"));
      var matcher = RSS_PATTERN.matcher(status);
      return matcher.find() ? Long.parseLong(matcher.group(1)) * 1024.0 : Double.NaN;
    } catch (IOException | NumberFormatException e) {
      return Double.NaN;
    }
  }
}
