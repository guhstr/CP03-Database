import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import FastAPI, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, Field

from app.db import db, r, criar_indices
from seed import seed

# Constantes de configuração e regras de negócio
CACHE_TTL = 60          # Req. 5: TTL de 60 segundos no cache de evento
RESERVA_TTL = 600       # Req. 6: Reserva temporária de 10 minutos (600s)
LIMITE_RESERVAS = 10    # Req. 8: Máximo de 10 reservas por minuto por usuário
JANELA_LIMITE = 60      # Janela de 60 segundos para o rate limit
RANKING_KEY = "ranking:eventos"   # Req. 7: Sorted Set no Redis
CANAL = "pedidos:confirmados"     # Bônus: Canal Redis Pub/Sub


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialização da API: garante a criação dos índices e seed inicial."""
    criar_indices()
    if db.eventos.count_documents({}) == 0:
        seed()
    yield


app = FastAPI(title="TicketFlash", lifespan=lifespan)


# ---------- Modelos Pydantic ----------
class Local(BaseModel):
    cidade: str
    endereco: str


class Setor(BaseModel):
    nome: str
    preco: float = Field(gt=0)
    capacidade: int = Field(gt=0)
    vendidos: int = 0


class EventoIn(BaseModel):
    nome: str
    categoria: str
    data: datetime
    local: Local
    atracoes: list[str] = []
    setores: list[Setor]


class EventoUpdate(BaseModel):
    nome: Optional[str] = None
    categoria: Optional[str] = None
    data: Optional[datetime] = None
    local: Optional[Local] = None
    atracoes: Optional[list[str]] = None
    setores: Optional[list[Setor]] = None


class UsuarioIn(BaseModel):
    nome: str
    email: str
    cidade: str


class ReservaIn(BaseModel):
    usuarioId: str
    eventoId: str
    setor: str
    quantidade: int = Field(gt=0, le=10)


class ConfirmarIn(BaseModel):
    usuarioId: str
    eventoId: str
    setor: str


# ---------- Funções Auxiliares ----------
def oid(valor: str) -> ObjectId:
    """Valida e converte uma string para ObjectId."""
    try:
        return ObjectId(valor)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail=f"ID inválido: '{valor}'")


def ser(obj):
    """Converte ObjectId e datetime para formatos nativos serializáveis em JSON."""
    if isinstance(obj, dict):
        return {k: ser(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [ser(v) for v in obj]
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def invalidar_cache(evento_id: str):
    """Req. 9: Remove a chave de cache do evento no Redis para garantir consistência."""
    r.delete(f"evento:{evento_id}")


# ---------- Rotas de Usuários ----------
@app.post("/usuarios", status_code=status.HTTP_201_CREATED)
def criar_usuario(u: UsuarioIn):
    """Cria um usuário validando unicidade de email através do índice único."""
    doc = u.model_dump() | {"dataCadastro": datetime.now(timezone.utc)}
    try:
        res = db.usuarios.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")
    return {"id": str(res.inserted_id), "mensagem": "Usuário criado com sucesso"}


@app.get("/usuarios")
def listar_usuarios(limit: int = 20):
    """Lista usuários cadastrados."""
    return [ser(u) for u in db.usuarios.find().limit(limit)]


# ---------- Req. 2: CRUD de Eventos ----------
@app.post("/eventos", status_code=status.HTTP_201_CREATED)
def criar_evento(e: EventoIn):
    """Cria um novo evento no MongoDB com setores embutidos."""
    res = db.eventos.insert_one(e.model_dump())
    return {"id": str(res.inserted_id), "mensagem": "Evento criado com sucesso"}


@app.get("/eventos")
def listar_eventos(categoria: Optional[str] = None, cidade: Optional[str] = None,
                   limit: int = Query(50, le=200)):
    """Lista eventos com filtros opcionais aplicados diretamente na consulta ao banco."""
    filtro = {}
    if categoria:
        filtro["categoria"] = categoria
    if cidade:
        filtro["local.cidade"] = cidade
    return [ser(e) for e in db.eventos.find(filtro).sort("data", 1).limit(limit)]


# Req. 7: Declarado antes de /eventos/{evento_id} para não colidir com o parâmetro de rota
@app.get("/eventos/ranking")
def ranking():
    """Retorna o Top 5 de eventos mais visualizados usando Redis Sorted Set."""
    top = r.zrevrange(RANKING_KEY, 0, 4, withscores=True)
    ids = [oid(i) for i, _ in top]
    nomes = {str(e["_id"]): e["nome"] for e in db.eventos.find({"_id": {"$in": ids}}, {"nome": 1})}
    return [{"posicao": n + 1, "eventoId": i, "nome": nomes.get(i), "visualizacoes": int(s)}
            for n, (i, s) in enumerate(top)]


# Req. 5 + 7: Cache-aside com indicação de origem e incremento no ranking
@app.get("/eventos/{evento_id}")
def buscar_evento(evento_id: str):
    """Busca evento pelo ID no Redis antes de consultar o MongoDB."""
    _id = oid(evento_id)
    key = f"evento:{evento_id}"
    cached = r.get(key)
    if cached:
        r.zincrby(RANKING_KEY, 1, evento_id)
        return {"origem": "cache", "evento": json.loads(cached)}

    doc = db.eventos.find_one({"_id": _id})
    if not doc:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    data = ser(doc)
    r.set(key, json.dumps(data), ex=CACHE_TTL)
    r.zincrby(RANKING_KEY, 1, evento_id)
    return {"origem": "banco", "evento": data}


# Req. 9: Invalidação de cache no update e no delete
@app.put("/eventos/{evento_id}")
def atualizar_evento(evento_id: str, e: EventoUpdate):
    """Atualiza dados do evento e invalida o cache no Redis."""
    campos = e.model_dump(exclude_unset=True)
    if not campos:
        raise HTTPException(status_code=400, detail="Nenhum campo fornecido para atualização")

    res = db.eventos.update_one({"_id": oid(evento_id)}, {"$set": campos})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    invalidar_cache(evento_id)
    return {"atualizado": True, "mensagem": "Evento atualizado e cache invalidado"}


@app.delete("/eventos/{evento_id}")
def remover_evento(evento_id: str):
    """Remove evento do banco, invalida cache e remove do ranking."""
    res = db.eventos.delete_one({"_id": oid(evento_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    invalidar_cache(evento_id)
    r.zrem(RANKING_KEY, evento_id)
    return {"removido": True, "mensagem": "Evento removido e cache invalidado"}


# ---------- Req. 4: Agregações no MongoDB ----------
@app.get("/relatorios/faturamento")
def faturamento():
    """Calcula o faturamento total por evento a partir dos pedidos confirmados via $lookup."""
    pipeline = [
        {"$match": {"status": "confirmado"}},
        {"$group": {"_id": "$eventoId", "faturamento": {"$sum": "$valorTotal"},
                    "pedidos": {"$sum": 1}}},
        {"$lookup": {"from": "eventos", "localField": "_id", "foreignField": "_id", "as": "evento"}},
        {"$unwind": "$evento"},
        {"$project": {"_id": 0, "eventoId": {"$toString": "$_id"}, "nome": "$evento.nome",
                      "faturamento": {"$round": ["$faturamento", 2]}, "pedidos": 1}},
        {"$sort": {"faturamento": -1}},
    ]
    return list(db.pedidos.aggregate(pipeline))


@app.get("/relatorios/ocupacao/{evento_id}")
def ocupacao(evento_id: str):
    """Calcula a taxa de ocupação percentual de cada setor de um evento."""
    pipeline = [
        {"$match": {"_id": oid(evento_id)}},
        {"$unwind": "$setores"},
        {"$project": {"_id": 0, "setor": "$setores.nome", "capacidade": "$setores.capacidade",
                      "vendidos": "$setores.vendidos",
                      "percentualVendido": {"$round": [
                          {"$multiply": [{"$divide": ["$setores.vendidos", "$setores.capacidade"]}, 100]}, 2]}}},
        {"$sort": {"percentualVendido": -1}},
    ]
    res = list(db.eventos.aggregate(pipeline))
    if not res:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    return res


# ---------- Req. 3: explain() ----------
@app.get("/admin/explain")
def explain(categoria: str = "Show"):
    """Exibe o winningPlan da consulta demonstrando o uso de IXSCAN no índice composto."""
    cursor = db.eventos.find({"categoria": categoria, "data": {"$gte": datetime(2020, 1, 1)}}).sort("data", 1)
    plano = cursor.explain()
    return ser(plano["queryPlanner"]["winningPlan"])


# ---------- Req. 8: Limite de Requisições (Rate Limit) ----------
def checar_limite(usuario_id: str):
    """Verifica se o usuário excedeu o limite de 10 reservas por minuto."""
    key = f"limite:reservas:{usuario_id}"
    n = r.incr(key)
    if r.ttl(key) == -1:  # Primeira requisição: define a expiração da janela
        r.expire(key, JANELA_LIMITE)
    if n > LIMITE_RESERVAS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Limite de {LIMITE_RESERVAS} reservas por minuto excedido",
            headers={"Retry-After": str(max(r.ttl(key), 1))}
        )


# ---------- Req. 6 + 10: Fluxo de Compra ----------
def chave_reserva(usuario_id, evento_id, setor):
    return f"reserva:{usuario_id}:{evento_id}:{setor}"


@app.post("/reservas", status_code=status.HTTP_201_CREATED)
def reservar(p: ReservaIn):
    """Cria uma reserva temporária de ingressos com TTL de 10 minutos no Redis."""
    checar_limite(p.usuarioId)
    if not db.usuarios.find_one({"_id": oid(p.usuarioId)}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    evento = db.eventos.find_one({"_id": oid(p.eventoId)})
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    setor = next((s for s in evento.get("setores", []) if s["nome"] == p.setor), None)
    if not setor:
        raise HTTPException(status_code=404, detail="Setor não encontrado")

    if setor["capacidade"] - setor["vendidos"] < p.quantidade:
        raise HTTPException(status_code=409, detail="Setor sem vagas suficientes")

    valor = json.dumps({"quantidade": p.quantidade, "preco": setor["preco"]})
    ok = r.set(chave_reserva(p.usuarioId, p.eventoId, p.setor), valor, nx=True, ex=RESERVA_TTL)
    if not ok:
        raise HTTPException(status_code=409, detail="Já existe uma reserva ativa pendente para este setor")

    return {
        "reservado": True,
        "expiraEmSegundos": RESERVA_TTL,
        "chave": chave_reserva(p.usuarioId, p.eventoId, p.setor)
    }


@app.post("/pedidos/confirmar", status_code=status.HTTP_201_CREATED)
def confirmar(p: ConfirmarIn):
    """
    Confirma pedido: consome reserva com GETDEL (410 se expirou),
    realiza incremento atômico de vendidos no MongoDB e publica no Pub/Sub.
    """
    usuario_id, evento_id = oid(p.usuarioId), oid(p.eventoId)

    # GETDEL: Lê e apaga a reserva atomicamente para prevenir confirmação dupla
    bruto = r.getdel(chave_reserva(p.usuarioId, p.eventoId, p.setor))
    if bruto is None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Reserva expirada ou inexistente")

    reserva = json.loads(bruto)
    qtd = reserva["quantidade"]

    # Incremento atômico com checagem de capacidade no próprio filtro
    res = db.eventos.update_one(
        {
            "_id": evento_id,
            "$expr": {
                "$anyElementTrue": {
                    "$map": {
                        "input": "$setores", "as": "s",
                        "in": {"$and": [{"$eq": ["$$s.nome", p.setor]},
                                        {"$lte": [{"$add": ["$$s.vendidos", qtd]}, "$$s.capacidade"]}]}
                    }
                }
            }
        },
        {"$inc": {"setores.$[s].vendidos": qtd}},
        array_filters=[{"s.nome": p.setor}],
    )

    if res.modified_count == 0:
        raise HTTPException(status_code=409, detail="Capacidade do setor esgotada")

    pedido = {
        "usuarioId": usuario_id,
        "eventoId": evento_id,
        "setor": p.setor,
        "quantidade": qtd,
        "valorTotal": round(qtd * reserva["preco"], 2),
        "status": "confirmado",
        "criadoEm": datetime.now(timezone.utc)
    }

    try:
        res = db.pedidos.insert_one(pedido)
    except Exception:
        # Compensação: desfaz o incremento caso a inserção do pedido falhe
        db.eventos.update_one(
            {"_id": evento_id},
            {"$inc": {"setores.$[s].vendidos": -qtd}},
            array_filters=[{"s.nome": p.setor}]
        )
        raise

    # Invalidação do cache pois a quantidade vendida foi alterada
    invalidar_cache(p.eventoId)

    # Bônus: Publicação no Pub/Sub
    r.publish(CANAL, json.dumps(ser({**pedido, "_id": res.inserted_id})))

    return {
        "pedidoId": str(res.inserted_id),
        "valorTotal": pedido["valorTotal"],
        "status": "confirmado"
    }
