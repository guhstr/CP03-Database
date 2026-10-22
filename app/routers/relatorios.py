from fastapi import APIRouter, HTTPException, status
from app.db import db, oid, ser

router = APIRouter(prefix="/relatorios", tags=["Relatórios e Agregações"])


@router.get("/faturamento", summary="Faturamento consolidado por evento (Req. 4)")
def relatorio_faturamento():
    """
    Req. 4 - Agregação no MongoDB:
    Calcula a soma do valor total dos pedidos com status 'confirmado' para cada evento,
    ordenado do maior faturamento para o menor, trazendo o nome do evento via $lookup.

    Operadores utilizados no pipeline:
    - $match: filtra apenas pedidos com status 'confirmado'
    - $group: agrupa por eventoId somando valorTotal e contando pedidos
    - $lookup: faz junção com a coleção 'eventos' para obter o nome do evento
    - $unwind: desmembra o array gerado pelo lookup
    - $project: formata os campos de saída e arredonda os valores monetários
    - $sort: ordena de forma decrescente pelo faturamento total
    """
    pipeline = [
        {"$match": {"status": "confirmado"}},
        {
            "$group": {
                "_id": "$eventoId",
                "faturamento": {"$sum": "$valorTotal"},
                "pedidosConfirmados": {"$sum": 1}
            }
        },
        {
            "$lookup": {
                "from": "eventos",
                "localField": "_id",
                "foreignField": "_id",
                "as": "evento"
            }
        },
        {"$unwind": "$evento"},
        {
            "$project": {
                "_id": 0,
                "eventoId": {"$toString": "$_id"},
                "nome": "$evento.nome",
                "categoria": "$evento.categoria",
                "faturamento": {"$round": ["$faturamento", 2]},
                "pedidosConfirmados": 1
            }
        },
        {"$sort": {"faturamento": -1}}
    ]

    resultado = list(db.pedidos.aggregate(pipeline))
    return resultado


@router.get("/ocupacao/{evento_id}", summary="Percentual de ocupação por setor de um evento (Req. 4)")
def relatorio_ocupacao(evento_id: str):
    """
    Req. 4 - Agregação no MongoDB:
    Calcula a taxa percentual de ocupação de cada setor de um determinado evento.

    Operadores utilizados no pipeline:
    - $match: localiza o evento específico pelo _id
    - $unwind: desmembra o array de setores para processar cada setor individualmente
    - $project: projeta o nome, capacidade, ingressos vendidos e calcula a taxa:
                (vendidos / capacidade) * 100
    - $sort: ordena os setores pelo percentual vendido em ordem decrescente
    """
    pipeline = [
        {"$match": {"_id": oid(evento_id)}},
        {"$unwind": "$setores"},
        {
            "$project": {
                "_id": 0,
                "setor": "$setores.nome",
                "capacidade": "$setores.capacidade",
                "vendidos": "$setores.vendidos",
                "vagasRestantes": {"$subtract": ["$setores.capacidade", "$setores.vendidos"]},
                "percentualVendido": {
                    "$round": [
                        {
                            "$multiply": [
                                {"$divide": ["$setores.vendidos", "$setores.capacidade"]},
                                100
                            ]
                        },
                        2
                    ]
                }
            }
        },
        {"$sort": {"percentualVendido": -1}}
    ]

    resultado = list(db.eventos.aggregate(pipeline))
    if not resultado:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    return resultado
