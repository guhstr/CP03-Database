import json
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.config import settings
from app.db import db, r, oid, ser, invalidar_cache
from app.models import EventoCreate, EventoUpdate

router = APIRouter(prefix="/eventos", tags=["Eventos"])


@router.post("", status_code=status.HTTP_201_CREATED, summary="Criar novo evento (Req. 2)")
def criar_evento(evento: EventoCreate):
    """Cria um novo evento no MongoDB com setores embutidos."""
    doc = evento.model_dump()
    res = db.eventos.insert_one(doc)
    return {"id": str(res.inserted_id), "mensagem": "Evento criado com sucesso"}


@router.get("", summary="Listar eventos com filtros opcionais (Req. 2)")
def listar_eventos(
    categoria: Optional[str] = Query(None, description="Filtrar por categoria do evento (ex: Show, Festival)"),
    cidade: Optional[str] = Query(None, description="Filtrar por cidade do local"),
    limit: int = Query(50, le=200, description="Limite máximo de registros retornados")
):
    """
    Lista eventos aplicando filtros diretamente na consulta ao banco MongoDB e
    ordenando cronologicamente por data (aproveitando o índice composto categoria_data).
    """
    filtro = {}
    if categoria:
        filtro["categoria"] = categoria
    if cidade:
        filtro["local.cidade"] = cidade

    cursor = db.eventos.find(filtro).sort("data", 1).limit(limit)
    return [ser(e) for e in cursor]


@router.get("/ranking", summary="Top 5 eventos mais visualizados (Req. 7)")
def ranking_eventos():
    """
    Req. 7: Devolve o Top 5 de eventos mais visualizados utilizando Redis Sorted Set (ZREVRANGE).
    A contagem é incrementada automaticamente via ZINCRBY a cada consulta de detalhes.
    """
    top = r.zrevrange(settings.RANKING_KEY, 0, 4, withscores=True)
    if not top:
        return []

    ids_obj = [oid(ev_id) for ev_id, _ in top]
    nomes_map = {
        str(e["_id"]): e["nome"]
        for e in db.eventos.find({"_id": {"$in": ids_obj}}, {"nome": 1})
    }

    resultado = []
    for posicao, (ev_id, score) in enumerate(top, start=1):
        resultado.append({
            "posicao": posicao,
            "eventoId": ev_id,
            "nome": nomes_map.get(ev_id, "Evento"),
            "visualizacoes": int(score)
        })
    return resultado


@router.get("/{evento_id}", summary="Buscar evento por ID com Cache-Aside e Ranking (Req. 5 e 7)")
def buscar_evento(evento_id: str):
    """
    Req. 5: Padrão Cache-Aside com chave 'evento:{id}' e TTL de 60 segundos.
    Retorna explicitamente o campo 'origem': 'cache' ou 'origem': 'banco'.
    Req. 7: Cada consulta incrementa as visualizações do evento no Redis Sorted Set (ZINCRBY).
    """
    _id = oid(evento_id)
    cache_key = f"evento:{evento_id}"

    # 1. Verifica cache no Redis
    cached = r.get(cache_key)
    if cached:
        r.zincrby(settings.RANKING_KEY, 1, evento_id)
        return {"origem": "cache", "evento": json.loads(cached)}

    # 2. Busca no MongoDB se houver cache miss
    doc = db.eventos.find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    data = ser(doc)

    # 3. Armazena no Redis com TTL de 60 segundos
    r.set(cache_key, json.dumps(data), ex=settings.CACHE_TTL)

    # 4. Incrementa ranking de visualizações
    r.zincrby(settings.RANKING_KEY, 1, evento_id)

    return {"origem": "banco", "evento": data}


@router.put("/{evento_id}", summary="Atualizar evento e invalidar cache (Req. 2 e 9)")
def atualizar_evento(evento_id: str, payload: EventoUpdate):
    """
    Req. 2: Atualiza os dados de um evento existente no MongoDB.
    Req. 9: Invalida a chave correspondente no Redis ('evento:{id}') para manter consistência.
    """
    campos = payload.model_dump(exclude_unset=True)
    if not campos:
        raise HTTPException(status_code=400, detail="Nenhum campo fornecido para atualização")

    res = db.eventos.update_one({"_id": oid(evento_id)}, {"$set": campos})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    # Invalidação do cache
    invalidar_cache(evento_id)

    return {"atualizado": True, "mensagem": "Evento atualizado e cache invalidado com sucesso"}


@router.delete("/{evento_id}", summary="Remover evento e invalidar cache/ranking (Req. 2 e 9)")
def remover_evento(evento_id: str):
    """
    Req. 2: Remove o evento do MongoDB.
    Req. 9: Invalida o cache no Redis ('evento:{id}') e remove do ranking de visualizações (ZREM).
    """
    res = db.eventos.delete_one({"_id": oid(evento_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    # Invalida cache e remove do ranking
    invalidar_cache(evento_id)
    r.zrem(settings.RANKING_KEY, evento_id)

    return {"removido": True, "mensagem": "Evento removido e cache invalidado com sucesso"}
