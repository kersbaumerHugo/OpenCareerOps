# Version Roadmap

## v0.1 — Source of Truth

### Objetivo:

"Sempre saber exatamente onde estou."

### Entrega:

 - Estado da transição
 - Próximos passos
 - Histórico
 - Relatório semanal
 - Priorização

## v0.2 — GitOps Career State

### Objetivo:

"Manter o estado da carreira versionado em Git e validado antes de cada alteração."

### Entrega:

 - ADR-0002: Git como fonte de verdade operacional
 - `career-state` privado com `state/current.json` (schema v1)
 - Validação automática por PR, usando o engine existente
 - Relatório semanal gerado por GitHub Actions, disponível como artifact privado
 - Histórico de alterações obtido por commits/PRs (sem duplicação de logs)
 - Notion e banco de dados fora do fluxo operacional

## v0.3 — Career Intelligence

### Objetivo:

"Começar a pensar."

### Entram:

 - análise de prioridades
 - identificação de gargalos
 - risco de atraso
 - Sugestão de próximos passos
 - Detecção de inconsistências

## v0.4 — Knowledge Engine

### Entram:

 - RAG
 - embeddings
 - vector database
 - leitura do GitHub
 - leitura do currículo
 - leitura das publicações

Agora ele passa a responder perguntas como:

"Já escrevi algo parecido?"

## v0.5 — ContentOps

Entram:

 - Geração de ideias
 - Calendário editorial
 - Revisão
 - Score de qualidade
 - Sugestões de imagens

## v0.6 — JobOps

Entram:

 - vagas
 - ATS
 - comparação currículo x vaga
 - score de aderência
 - acompanhamento de candidaturas

## v1.0 — OpenCareerOps

Primeira versão pública.