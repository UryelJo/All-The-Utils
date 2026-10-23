# Documentação Oficial e Base de Conhecimento — All the Utils

Bem-vindo à pasta de documentação e preservação de contexto do **All the Utils**.

Este diretório foi estruturado no raiz do projeto para manter o registro contínuo de todas as implementações, decisões de arquitetura e instruções para prompts futuros, assegurando que o projeto nunca sofra com inconsistências ou perdas de requisitos.

---

## Índice dos Documentos

1. **[registro_tecnico.md](registro_tecnico.md)**
   - Arquitetura geral do software, padrão de separação Core/UI/Tools.
   - Contratos dos plugins (`Tool` e `FileTool`).
   - Estado de conclusão das fases do projeto.

2. **[catalogo_ferramentas.md](catalogo_ferramentas.md)**
   - Inventário minucioso de todas as ferramentas implementadas no sistema.
   - IDs, parâmetros de entrada, tipos de saída e recursos gráficos.

3. **[contexto_para_prompts.md](contexto_para_prompts.md)**
   - Guia rápido de contexto para ser utilizado em novos prompts ou por novos modelos de IA.
   - Regras de estilo de UI (Fluent, Segoe UI, sem emojis, pt-BR).
   - Exemplos práticos de código para criar novas ferramentas em lote (`FileTool`) ou interativas (`Tool`).
   - Comandos úteis de teste e execução.
