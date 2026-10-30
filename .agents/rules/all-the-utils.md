---
trigger: always_on
---

**REGRAS DE IMPLEMENTAÇÃO (NOVAS FERRAMENTAS):**

1. **Contexto:** Leia `/docs/contexto_para_prompts.md` para alinhar com o escopo do projeto.
2. **Duplicidade:** Consulte `/docs/catalogo_ferramentas.md` para evitar recriar lógicas existentes.
3. **Desenvolvimento:**
   - Crie código modular, seguindo a PEP 8 e aplicando _Type Hints_ rigorosamente.
   - Isole a lógica da ferramenta da interface de usuário (UI).
   - **Contrato `FileTool` e `ItemResult`:** Em ferramentas `FileTool`, `process(src, dst, params, ctx)` NUNCA deve ler widgets Qt diretamente (use apenas `params`, pois executa em worker/background) e DEVE retornar `ItemResult` estritamente com os campos oficiais de `core/registry.py` (`success`, `source_path`, `output_path`, `message`, `error`, `bytes_in`, `bytes_out`), implementando `output_ext(params)` sempre que o formato de saída diferir da entrada.
   - **Padrão Visual de UI:** Ao criar ou repaginar telas e componentes de UI, consulte as referências em `/docs/visual/` (quando aplicável), priorizando layout bem integrado, espaçamento/dimensionamento proporcional, hierarquia tipográfica limpa e ausência total de emojis em controles.
   - **Credenciais:** Registre qualquer nova chave de API EXCLUSIVAMENTE nas configurações globais de `api_tokens`. Nunca faça _hardcode_ de chaves no código da ferramenta.
   - Implemente customizações através de argumentos bem definidos ou arquivos de configuração, evitando _hardcode_ e complexidade desnecessária.
4. **Documentação:** Ao finalizar, registre a nova ferramenta no `catalogo_ferramentas.md`, mantendo a estrutura padrão do arquivo.

**DIRETRIZES DE QUALIDADE DE TESTES (ANTI-GAMBIARRA):**
1. **Princípio da Validação do Efeito Real (Black-Box Testing):**
   - Nunca considere um teste aprovado apenas porque `mock.called == True` ou `len(items) >= 1`.
   - Se a ferramenta gera um arquivo (PDF, imagem, áudio, ZIP), o teste DEVE abrir o arquivo resultante com o leitor correspondente e validar o conteúdo interno (ex.: extrair o texto do PDF com `PdfReader`, conferir a taxa de amostragem em Hz do áudio, descompactar e ler o hash do arquivo no ZIP).
   - Se a ferramenta move arquivos ou cria junções, o teste DEVE ler o arquivo real através do link e comprovar que o dado é idêntico.
   - Toda ferramenta `FileTool` DEVE ter pelo menos um teste de integração executando `tool.process` através do `execute_batch` (`core/batch.py`), validando o contrato real de `ItemResult` (sucesso, cancelamento e falha) além dos testes de `logic.py`.
2. **Proibição de Asserções Frouxas:**
   - Proibido usar `assert True`, `assert obj is not None` ou `>=` quando o valor esperado é determinístico (`==`).
   - Todo teste deve incluir obrigatoriamente:
     a) O "Happy Path" com verificação de saída exata.
     b) Casos de borda (edge cases: strings vazias, anos bissextos, limites).
     c) Cenários de falha (entradas maliciosas ou inválidas, como caminhos aninhados que causariam recursão infinita).
3. **Isolamento de Rede sem Falsos Positivos:**
   - Testes unitários NUNCA devem fazer chamadas reais para a internet.
   - Os mocks de rede DEVEM testar cenários de falha reais do mundo real: respostas HTML de proxy (502 Bad Gateway), timeouts e JSONs malformados, garantindo que o código não quebre com `JSONDecodeError` na UI.
