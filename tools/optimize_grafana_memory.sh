#!/usr/bin/env bash
# ==============================================================================
# Optimización de Memoria para Grafana en ADA
# Reduce el consumo de RAM de ~650MB a ~120-180MB desactivando:
# 1. Procesos gRPC satélites no utilizados (Elasticsearch, Loki, MySQL, etc.)
# 2. Motor interno de alertas unificadas (Unified Alerting)
# 3. Telemetría y chequeos en segundo plano
# 4. Limitando la retención de memoria de Go (GOMEMLIMIT / GOGC)
# ==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
  echo "❌ Por favor ejecuta este script con sudo: sudo bash $0"
  exit 1
fi

echo "🚀 [1/4] Moviendo plugins satélites no utilizados..."
mkdir -p /var/lib/grafana/plugins-bundled-disabled
for plugin in elasticsearch grafana-postgresql-datasource grafana-pyroscope-datasource influxdb jaeger loki mssql mysql opentsdb stackdriver tempo zipkin; do
  if [ -d "/var/lib/grafana/plugins-bundled/$plugin" ]; then
    echo "  - Desactivando plugin: $plugin"
    mv "/var/lib/grafana/plugins-bundled/$plugin" /var/lib/grafana/plugins-bundled-disabled/
  fi
done

echo "⚙️  [2/4] Optimizando configuración en /etc/grafana/grafana.ini..."
# Desactivar unified_alerting
if grep -q "\[unified_alerting\]" /etc/grafana/grafana.ini; then
  sed -i '/\[unified_alerting\]/,/\[/ s/.*enabled = .*/enabled = false/' /etc/grafana/grafana.ini
else
  cat << 'EOF' >> /etc/grafana/grafana.ini

[unified_alerting]
enabled = false
EOF
fi

# Desactivar alerting clásico
if grep -q "\[alerting\]" /etc/grafana/grafana.ini; then
  sed -i '/\[alerting\]/,/\[/ s/.*enabled = .*/enabled = false/' /etc/grafana/grafana.ini
fi

# Desactivar analytics
sed -i 's/.*reporting_enabled = .*/reporting_enabled = false/' /etc/grafana/grafana.ini
sed -i 's/.*check_for_updates = .*/check_for_updates = false/' /etc/grafana/grafana.ini
sed -i 's/.*check_for_plugin_updates = .*/check_for_plugin_updates = false/' /etc/grafana/grafana.ini

echo "📦 [3/4] Configurando límites de memoria de Go en systemd..."
mkdir -p /etc/systemd/system/grafana-server.service.d
cat << 'EOF' > /etc/systemd/system/grafana-server.service.d/memory-limit.conf
[Service]
Environment="GOMEMLIMIT=150MiB"
Environment="GOGC=50"
EOF

echo "🔄 [4/4] Recargando systemd y reiniciando grafana-server..."
systemctl daemon-reload
systemctl restart grafana-server

echo "✅ ¡Grafana optimizado con éxito!"
echo ""
echo "📊 Procesos de Grafana actuales:"
ps -u grafana -o pid,rss,cmd --sort -rss
