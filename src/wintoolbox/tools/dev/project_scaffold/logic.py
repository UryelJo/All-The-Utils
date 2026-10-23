"""
Lógica pura de geração de templates, scaffolding de repositórios e licenças de software.
Zero acoplamento com bibliotecas de UI.
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from wintoolbox.core.logging_setup import get_logger

_log = get_logger("dev.project_scaffold")

GITIGNORE_TEMPLATES: Dict[str, str] = {
    "Python": """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual Environments
.venv/
venv/
ENV/
env/

# Testing and Coverage
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
pytestdebug.log
""",
    "Node.js / TypeScript": """# Logs
logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
lerna-debug.log*

# Diagnostic reports
report.[0-9]*.[0-9]*.[0-9]*.[0-9]*.json

# Runtime data
pids
*.pid
*.seed
*.pid.lock

# Dependency directories
node_modules/
jspm_packages/

# TypeScript cache & dist
*.tsbuildinfo
dist/
build/
out/
.next/
.nuxt/

# Environment
.env
.env.local
.env.development.local
.env.test.local
.env.production.local
""",
    "Rust": """/target/
**/*.rs.bk
Cargo.lock
""",
    "Go": """# Binaries for programs and plugins
*.exe
*.exe~
*.dll
*.so
*.dylib

# Test binary, built with `go test -c`
*.test

# Output of the go coverage tool
*.out

# Dependency directories
vendor/
bin/
""",
    "C# / .NET": """## Visual Studio / MSBuild
[Bb]in/
[Oo]bj/
[Ll]og/
[Ll]ogs/

# User-specific files
*.rsuser
*.suo
*.user
*.userosscache
*.sln.docstates

# Visual Studio Code & Studio cache
.vs/
.vscode/
*.DotSettings.user
""",
    "C / C++": """# Compiled Object files
*.slo
*.lo
*.o
*.obj

# Precompiled Headers
*.gch
*.pch

# Compiled Dynamic libraries
*.so
*.dylib
*.dll

# Compiled Static libraries
*.lai
*.la
*.a
*.lib

# Executables
*.exe
*.out
*.app

# CMake build folders
build/
cmake-build-*/
""",
    "Flutter / Dart": """# Miscellaneous
*.class
*.log
*.pyc
*.swp
.DS_Store
.atom/
.buildlog/
.history
.svn/

# IntelliJ related
*.iml
*.ipr
*.iws
.idea/

# Flutter/Dart/Pub related
**/doc/api/
.dart_tool/
.flutter-plugins
.flutter-plugins-dependencies
.packages
.pub-cache/
.pub/
/build/
"""
}

GENERAL_GITIGNORE = """
# IDEs and Editors
.vscode/
.idea/
*.sublime-project
*.sublime-workspace

# Operating System Files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
desktop.ini
"""

EDITORCONFIG_TEMPLATE = """# http://editorconfig.org
root = true

[*]
indent_style = space
indent_size = 4
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.{json,yml,yaml,md,js,ts,jsx,tsx,css,scss,html}]
indent_size = 2

[Makefile]
indent_style = tab
"""

LICENSE_TEMPLATES: Dict[str, str] = {
    "MIT": """MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
""",
    "Apache 2.0": """Copyright {year} {author}

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
""",
    "GPL v3": """GNU GENERAL PUBLIC LICENSE
Version 3, 29 June 2007

Copyright (C) {year} {author}

Everyone is permitted to copy and distribute verbatim copies
of this license document, but changing it is not allowed.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
""",
    "BSD 3-Clause": """Copyright (c) {year}, {author}
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
""",
    "The Unlicense": """This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
"""
}


def get_available_languages() -> List[str]:
    return list(GITIGNORE_TEMPLATES.keys())


def get_available_licenses() -> List[str]:
    return list(LICENSE_TEMPLATES.keys())


def get_gitignore_content(language: str, include_general: bool = True) -> str:
    content = GITIGNORE_TEMPLATES.get(language, "")
    if include_general:
        content = content + "\n" + GENERAL_GITIGNORE
    return content.strip() + "\n"


def get_license_content(license_type: str, author: str, year: Optional[int] = None) -> str:
    y = year or datetime.now().year
    auth = author.strip() or "Nome do Autor / Organização"
    template = LICENSE_TEMPLATES.get(license_type, LICENSE_TEMPLATES["MIT"])
    return template.format(year=y, author=auth)


def get_readme_content(project_name: str, description: str, author: str, license_type: str) -> str:
    name = project_name.strip() or "Meu Projeto"
    desc = description.strip() or "Descrição concisa do projeto e seus objetivos principais."
    auth = author.strip() or "Autor"

    return f"""# {name}

{desc}

---

## Recursos e Funcionalidades

- Arquitetura moderna e código limpo
- Configuração pronta para desenvolvimento ágil
- Testes automatizados integrados

## Pré-requisitos

- Git instalado
- Ambiente de desenvolvimento configurado

## Instalação e Execução

```bash
# Clone o repositório
git clone https://github.com/{auth.lower().replace(' ', '')}/{name.lower().replace(' ', '-')}.git

# Acesse o diretório
cd {name.lower().replace(' ', '-')}
```

## Licença

Distribuído sob a licença **{license_type}**. Veja o arquivo `LICENSE` para mais detalhes.

---
Desenvolvido por **{auth}**.
"""


def generate_scaffold_files(
    target_dir: Path,
    project_name: str,
    description: str,
    author: str,
    language: str,
    license_type: str,
    create_gitignore: bool = True,
    create_license: bool = True,
    create_readme: bool = True,
    create_editorconfig: bool = True,
    create_env_example: bool = True
) -> List[Tuple[str, bool]]:
    """
    Cria os arquivos de scaffold no diretório especificado.
    Retorna lista de tuplas: (nome_do_arquivo, sobrescrito_ou_novo).
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    results: List[Tuple[str, bool]] = []

    files_to_write: Dict[str, str] = {}

    if create_gitignore:
        files_to_write[".gitignore"] = get_gitignore_content(language, include_general=True)

    if create_license:
        files_to_write["LICENSE"] = get_license_content(license_type, author)

    if create_readme:
        files_to_write["README.md"] = get_readme_content(project_name, description, author, license_type)

    if create_editorconfig:
        files_to_write[".editorconfig"] = EDITORCONFIG_TEMPLATE.strip() + "\n"

    if create_env_example:
        env_content = f"# Variáveis de Ambiente para {project_name or 'Projeto'}\nENV=development\nDEBUG=True\nAPI_KEY=sua_chave_aqui\n"
        files_to_write[".env.example"] = env_content

    for filename, content in files_to_write.items():
        file_path = target_dir / filename
        existed = file_path.exists()
        file_path.write_text(content, encoding="utf-8")
        results.append((filename, existed))

    return results
