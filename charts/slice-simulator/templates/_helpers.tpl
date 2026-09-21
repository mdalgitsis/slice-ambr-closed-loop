{{- define "slice-simulator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "slice-simulator.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "slice-simulator.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "slice-simulator.labels" -}}
app.kubernetes.io/name: {{ include "slice-simulator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "slice-simulator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "slice-simulator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
