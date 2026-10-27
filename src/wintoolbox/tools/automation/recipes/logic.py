"""
Lógica pura para o mecanismo de Receitas de Automação (Pipeline de Processamento).
Permite encadear etapas de processamento de arquivos e dados de ferramentas registradas.
Desacoplada de frameworks de interface gráfica.
"""
from dataclasses import asdict, dataclass, field
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional


@dataclass
class RecipeStep:
    """Representa uma etapa individual em uma receita de automação."""
    tool_id: str
    tool_name: str
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Recipe:
    """Receita de automação contendo uma sequência ordenada de etapas."""
    id: str
    name: str
    description: str
    steps: List[RecipeStep] = field(default_factory=list)


def recipe_to_dict(recipe: Recipe) -> Dict[str, Any]:
    """Serializa uma receita para dicionário Python."""
    return asdict(recipe)


def dict_to_recipe(data: Dict[str, Any]) -> Recipe:
    """Desserializa um dicionário para objeto Recipe."""
    steps = [
        RecipeStep(
            tool_id=s.get("tool_id", ""),
            tool_name=s.get("tool_name", ""),
            options=s.get("options", {})
        )
        for s in data.get("steps", [])
    ]
    return Recipe(
        id=data.get("id", ""),
        name=data.get("name", "Sem Nome"),
        description=data.get("description", ""),
        steps=steps
    )


def save_recipes_json(recipes: List[Recipe], filepath: str) -> None:
    """Salva lista de receitas em arquivo JSON."""
    raw = [recipe_to_dict(r) for r in recipes]
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)


def load_recipes_json(filepath: str) -> List[Recipe]:
    """Carrega lista de receitas de um arquivo JSON."""
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
            return [dict_to_recipe(d) for d in raw if isinstance(d, dict)]
    except Exception:
        return []


def execute_pipeline(
    recipe: Recipe,
    input_files: List[str],
    process_fn: Callable[[str, str, Dict[str, Any]], Optional[str]],
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Any]:
    """
    Executa a sequência de etapas de uma receita sobre uma lista de arquivos de entrada.
    process_fn: Função chamada para cada arquivo e etapa -> process_fn(tool_id, file_path, options) -> output_file_path.
    """
    start_time = time.time()
    current_files = list(input_files)
    total_steps = len(recipe.steps)
    step_reports = []

    for step_idx, step in enumerate(recipe.steps, 1):
        step_outputs = []
        step_errors = []

        if progress_callback:
            progress_callback(step_idx, total_steps, f"Executando {step.tool_name}...")

        for file_path in current_files:
            if not os.path.exists(file_path):
                step_errors.append(f"Arquivo não encontrado: {file_path}")
                continue
            try:
                out_path = process_fn(step.tool_id, file_path, step.options)
                if out_path and os.path.exists(out_path):
                    step_outputs.append(out_path)
                else:
                    # Se não produziu novo arquivo, mantém o original
                    step_outputs.append(file_path)
            except Exception as e:
                step_errors.append(f"Erro em {os.path.basename(file_path)}: {str(e)}")

        step_reports.append({
            "step_index": step_idx,
            "tool_id": step.tool_id,
            "tool_name": step.tool_name,
            "inputs_count": len(current_files),
            "outputs_count": len(step_outputs),
            "errors": step_errors
        })

        # Os arquivos de saída desta etapa tornam-se a entrada da próxima etapa
        if step_outputs:
            current_files = step_outputs

    duration = round(time.time() - start_time, 2)
    return {
        "recipe_name": recipe.name,
        "duration_seconds": duration,
        "final_files": current_files,
        "step_reports": step_reports,
        "success": all(len(s["errors"]) == 0 for s in step_reports)
    }
