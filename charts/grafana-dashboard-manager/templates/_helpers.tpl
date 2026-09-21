{{- define "gdm.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "gdm.labels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{/*
Shared pod spec. The create and delete Jobs differ only in their args, so
keeping one definition means the delete hook cannot drift from the create one.
*/}}
{{- define "gdm.jobPodSpec" -}}
{{- if not .Values.grafana.existingSecret -}}
{{- fail "grafana.existingSecret is required: create a Secret holding the Grafana service account token and name it here." -}}
{{- end -}}
restartPolicy: Never
{{- with .Values.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
containers:
  - name: dashboard-manager
    image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
    imagePullPolicy: {{ .Values.image.pullPolicy }}
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
          - ALL
    env:
      - name: GRAFANA_URL
        value: {{ .Values.grafana.url | quote }}
      - name: GRAFANA_SERVICE_ACCOUNT_TOKEN
        valueFrom:
          secretKeyRef:
            name: {{ .Values.grafana.existingSecret }}
            key: {{ .Values.grafana.tokenKey }}
{{- end -}}
