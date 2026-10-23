---
trigger: always_on
---

**REGRAS DE IMPLEMENTAÇÃO (NOVAS FERRAMENTAS):**

1. **Contexto:** Leia `/docs/contexto_para_prompts.md` para alinhar com o escopo do projeto.
2. **Duplicidade:** Consulte `/docs/catalogo_ferramentas.md` para evitar recriar lógicas existentes.
3. **Desenvolvimento:**
   - Crie código modular, seguindo a PEP 8 e aplicando _Type Hints_ rigorosamente.
   - Isole a lógica da ferramenta da interface de usuário (UI).
   - **Credenciais:** Registre qualquer nova chave de API EXCLUSIVAMENTE nas configurações globais de `api_tokens`. Nunca faça _hardcode_ de chaves no código da ferramenta.
   - Implemente customizações através de argumentos bem definidos ou arquivos de configuração, evitando _hardcode_ e complexidade desnecessária.
4. **Documentação:** Ao finalizar, registre a nova ferramenta no `catalogo_ferramentas.md`, mantendo a estrutura padrão do arquivo.
