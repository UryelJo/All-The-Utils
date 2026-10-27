"""
Testes unitários para o pipeline de receitas de automação.
Diretrizes Anti-Gambiarra: Validação determinística de execução de etapas em sequência.
"""
from wintoolbox.tools.automation.recipes.logic import (
    Recipe,
    RecipeStep,
    execute_pipeline,
    load_recipes_json,
    save_recipes_json,
)


def test_recipe_pipeline_execution(tmp_path):
    # Cria arquivo inicial de teste
    f1 = tmp_path / "teste.txt"
    f1.write_text("conteúdo original", encoding="utf-8")

    r = Recipe(
        id="rec_1",
        name="Pipeline de Teste",
        description="Pipeline sintético",
        steps=[
            RecipeStep(tool_id="step1", tool_name="Etapa 1"),
            RecipeStep(tool_id="step2", tool_name="Etapa 2")
        ]
    )

    steps_called = []

    def mock_proc(t_id: str, path: str, options: dict):
        steps_called.append((t_id, path))
        return path

    res = execute_pipeline(r, [str(f1)], mock_proc)

    assert res["success"] is True
    assert len(steps_called) == 2
    assert steps_called[0] == ("step1", str(f1))
    assert steps_called[1] == ("step2", str(f1))
    assert len(res["final_files"]) == 1


def test_recipe_json_serialization(tmp_path):
    p = tmp_path / "recipes.json"
    recipes = [
        Recipe(
            id="r1",
            name="R1",
            description="D1",
            steps=[RecipeStep("t1", "T1")]
        )
    ]
    save_recipes_json(recipes, str(p))
    assert p.exists()

    loaded = load_recipes_json(str(p))
    assert len(loaded) == 1
    assert loaded[0].id == "r1"
    assert loaded[0].name == "R1"
    assert len(loaded[0].steps) == 1
    assert loaded[0].steps[0].tool_id == "t1"
