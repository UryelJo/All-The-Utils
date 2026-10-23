# 🧰 WinToolbox - Caixa de Ferramentas para Windows

Aplicativo modular e rápido para Windows desenvolvido em Python utilizando **CustomTkinter**, **Pillow** e **psutil**.

---

## 🚀 Funcionalidades Inclusas

1. **🖼️ Conversor de Imagens**:
   - Converte imagens individuais ou em lote.
   - Formatos suportados de saída: `PNG`, `JPG`, `WEBP`, `ICO`, `BMP`, `TIFF`, `PDF`.
   - Ajuste de qualidade de compressão (JPEG/WEBP).
   - Conversão segura (canais de transparência RGBA tratados automaticamente para JPEG/PDF).

2. **🛠️ Ferramentas & Manutenção do Windows**:
   - **Otimização de Disco**: Otimização e desfragmentação (`defrag C: /O`) com log em tempo real.
   - **Limpeza de Arquivos Temporários**: Libera espaço apagando resíduos do `%TEMP%` e atalho para Limpeza de Disco nativa.
   - **Diagnóstico e Reparo do Sistema**: Verificação e reparação de integridade de arquivos do Windows (`sfc /scannow`).
   - **Limpeza de DNS**: `ipconfig /flushdns` integrado.
   - Detecção e botão para elevar privilégios para Administrador (UAC).

3. **📊 Monitor do Sistema**:
   - Acompanhamento em tempo real (atualização a cada 2 segundos) de uso de CPU, núcleos e Memória RAM.
   - Listagem automática de todas as unidades de armazenamento com espaço livre, usado e porcentagem.

---

## 💻 Como Executar

### Opção 1: Via atalho
Basta dar dois cliques no arquivo `iniciar.bat`.

### Opção 2: Via terminal
```bash
cd C:\Users\uryel\source\repos\WinToolbox
python main.py
```

---

## 📦 Como Gerar o Executável (.exe)

Basta dar dois cliques em `gerar_exe.bat` ou executar:
```bash
pyinstaller --noconfirm --onedir --windowed --uac-admin --name "WinToolbox" --collect-all customtkinter main.py
```
O executável final estará dentro da pasta `dist/WinToolbox/WinToolbox.exe`.
