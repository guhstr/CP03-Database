from datetime import datetime
from fastapi import APIRouter, Query
from app.db import db, ser

router = APIRouter(prefix="/admin", tags=["Administração e Diagnóstico"])


@router.get("/explain", summary="Plano de execução do índice composto no MongoDB (Req. 3)")
def explain_indice_composto(
    categoria: str = Query("Show", description="Categoria a ser filtrada para acionar o índice composto")
):
    """
    Req. 3 - Verificação do plano de execução (explain()):
    Executa uma consulta indexada com filtro por 'categoria' e intervalo ordenado por 'data'.
    Retorna o 'winningPlan' demonstrando o uso do estágio IXSCAN com o índice 'categoria_data'
    em vez de COLLSCAN (varredura completa da coleção).
    """
    data_limite = datetime(2020, 1, 1)
    cursor = db.eventos.find(
        {"categoria": categoria, "data": {"$gte": data_limite}}
    ).sort("data", 1)

    plano_execucao = cursor.explain()
    winning_plan = plano_execucao.get("queryPlanner", {}).get("winningPlan", {})

    return {
        "consulta": {
            "filtro": {"categoria": categoria, "data": {"$gte": "2020-01-01T00:00:00"}},
            "ordenacao": {"data": 1}
        },
        "planoExecucao": ser(winning_plan)
    }
