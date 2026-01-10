{{/*
Expand the name of the chart.
*/}}
{{- define "inres.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "inres.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "inres.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "inres.labels" -}}
helm.sh/chart: {{ include "inres.chart" . }}
{{ include "inres.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "inres.selectorLabels" -}}
app.kubernetes.io/name: {{ include "inres.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "inres.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "inres.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}


{{/*
Component-scoped fullname: <release>-<chart|override>-<component>
*/}}
{{- define "inres.componentFullname" -}}
{{- $root := .root -}}
{{- $comp := .name -}}
{{- printf "%s-%s" (include "inres.fullname" $root) $comp | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{/*
Component selector labels
*/}}
{{- define "inres.componentSelectorLabels" -}}
app.kubernetes.io/name: {{ include "inres.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .name }}
{{- end }}

{{/*
Component common labels
*/}}
{{- define "inres.componentLabels" -}}
helm.sh/chart: {{ include "inres.chart" .root }}
{{ include "inres.componentSelectorLabels" . }}
{{- if .root.Chart.AppVersion }}
app.kubernetes.io/version: {{ .root.Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .root.Release.Service }}
{{- end }}
