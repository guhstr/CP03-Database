# TicketFlash API — MongoDB + Redis com Python (FastAPI)

> **FIAP — Faculdade de Informática e Administração Paulista**  
> **Curso:** Superior de Tecnologia em Análise e Desenvolvimento de Sistemas  
> **Disciplina:** Mastering Relational and Non-Relational Database | **Turma:** 2TDSPG  
> **Professor:** Vergílio Santos  
> **Avaliação:** Checkpoint 3 — Projeto Prático: MongoDB + Redis com Python  

---

## 👥 Integrantes do Grupo

| RM | Nome Completo | Turma |
|:---|:---|:---:|
| **RM 561650** | **Gustavo Arthur Carvalho Sartori** | 2TDSPG |
| **RM 565771** | **Erik Naoki** | 2TDSPG |
| **RM 562267** | **Gutemberg Rocha** | 2TDSPG |
| **RM 564361** | **João Henrique** | 2TDSPG |
| **RM 561171** | **Juliana da Silva** | 2TDSPG |

---

## 🚀 Como Executar o Projeto

O projeto foi totalmente conteinerizado e está preparado para subir com um **único comando**:

```bash
docker compose up --build
```

### Serviços Inicializados:
1. **`api`** (FastAPI): Porta `8000` (Documentação Swagger interativa em: `http://localhost:8000/docs` e Redoc em `http://localhost:8000/redoc`).
2. **`mongo`** (MongoDB 7): Porta `27017` com volume persistente `ticketflash_mongo_data`.
3. **`redis`** (Redis 7 Alpine): Porta `6379`.

> **Seed Automático:** Caso o MongoDB esteja vazio na inicialização, a API detecta e roda o script `seed.py` automaticamente, gerando **16 eventos**, **30 usuários** e **80 pedidos** (superando os requisitos mínimos de 10 eventos, 20 usuários e 50 pedidos).

Para rodar o seed manualmente a qualquer momento:
```bash
docker compose exec api python seed.py
```

### 📢 Bônus: Assinante Pub/Sub (em outro terminal)
Para visualizar os pedidos confirmados em tempo real via Redis Pub/Sub:
```bash
docker compose exec api python subscriber.py
```

### 🧪 Testes Automatizados
Para executar a suite de testes ponta a ponta validando todos os requisitos:
```bash
docker compose exec api python tests/test_fluxo_completo.py
```

---

## 📌 Tabela de Endpoints

| Método | Rota | Descrição | Status Sucesso | Status Erro |
|:---|:---|:---|:---:|:---:|
| `GET` | `/` | Informações da API e status do sistema | 200 OK | — |
| `GET` | `/health` | Conectividade ativa com MongoDB e Redis | 200 OK | 500 |
| `POST` | `/usuarios` | Cria usuário validando e-mail único | 201 Created | 409 Conflict |
| `GET` | `/usuarios` | Lista usuários cadastrados com limite | 200 OK | — |
| `POST` | `/eventos` | Cria evento com setores embutidos (Req. 2) | 201 Created | 422 |
| `GET` | `/eventos` | Lista eventos com filtros opcionais (`categoria` e `cidade`) ordenados por data | 200 OK | — |
| `GET` | `/eventos/ranking` | Top 5 eventos mais visualizados via Redis Sorted Set (Req. 7) | 200 OK | — |
| `GET` | `/eventos/{id}` | Cache-Aside: busca no Redis; se falhar, busca no Mongo, grava com TTL 60s, incrementa visualizações e indica `"origem": "cache"` ou `"banco"` (Req. 5 e 7) | 200 OK | 400, 404 |
| `PUT` | `/eventos/{id}` | Atualiza evento no Mongo e invalida a chave de cache no Redis (Req. 2 e 9) | 200 OK | 400, 404 |
| `DELETE` | `/eventos/{id}` | Remove evento no Mongo, invalida cache e remove do ranking no Redis (Req. 2 e 9) | 200 OK | 400, 404 |
| `POST` | `/reservas` | Bloqueia ingressos temporariamente via `SET NX EX 600` (10 min) e checa rate limit de 10 req/min (Req. 6, 8 e 10) | 201 Created | 400, 404, 409, 429 |
| `POST` | `/pedidos/confirmar` | Confirma compra: remove reserva com `GETDEL` (410 se expirou), incrementa `vendidos` com `$inc` atômico checando capacidade e publica no Pub/Sub (Req. 10 e Bônus) | 201 Created | 400, 409, 410 Gone |
| `GET` | `/relatorios/faturamento` | Relatório consolidado: soma de faturamento dos pedidos confirmados por evento via `$group`, `$lookup` e `$sort` (Req. 4) | 200 OK | — |
| `GET` | `/relatorios/ocupacao/{id}`| Relatório de taxa de ocupação (%) de cada setor de um evento via `$unwind` e `$project` (Req. 4) | 200 OK | 400, 404 |
| `GET` | `/admin/explain` | Retorna o `winningPlan` da consulta indexada demonstrando uso de `IXSCAN` no índice composto (Req. 3) | 200 OK | — |

---

## 🏛️ Requisito 1 — Modelagem e Justificativas (Embutir vs. Referenciar)

A modelagem de dados foi desenhada considerando os padrões de acesso de alta concorrência da TicketFlash:

### 1. Setores, Local e Atrações Embutidos em `eventos` (Embedding)
* **Alta coesão e cardinalidade 1:Poucos:** Os setores (`nome`, `preco`, `capacidade`, `vendidos`), o endereço do local e o array de atrações pertencem exclusivamente àquele evento e raramente ultrapassam algumas dezenas de itens.
* **Leituras atômicas e performance:** A página de detalhes de um evento é o recurso mais requisitado do sistema. Embutir os setores elimina a necessidade de joins caros (`$lookup`), trazendo todos os dados necessários em uma única leitura indexada.
* **Atomicidade nas compras:** Permite aplicar o operador `$inc` condicional diretamente no subdocumento do setor dentro do documento do evento, garantindo que a checagem de vagas e o incremento ocorram de forma atômica no MongoDB sem locks distribuídos.

### 2. `pedidos` Referenciando `usuarioId` e `eventoId` (Referencing)
* **Cardinalidade 1:N com crescimento ilimitado:** Um evento ou usuário pode gerar milhares ou milhões de pedidos ao longo do tempo. Se os pedidos fossem embutidos, ultrapassariam facilmente o limite rígido de 16 MB por documento do BSON (padrão anti-pattern *Unbounded Arrays*).
* **Consultas e relatórios multidirecionais:** Pedidos precisam ser consultados e agregados por usuário (histórico do cliente) e por evento (relatórios financeiros e de faturamento), justificando uma coleção independente com índices próprios.

### 3. `usuarios` como Coleção Separada
* **Entidade mestre:** Possui ciclo de vida independente, regras de autenticação e garantia de unicidade de e-mail através de um índice único.

---

## ⚡ Redis — Estruturas de Dados e Chaves

| Chave | Estrutura Redis | TTL / Expiração | Finalidade no Sistema |
|:---|:---|:---:|:---|
| `evento:{id}` | `String` (JSON) | 60 segundos | **Cache-aside** da página de detalhes do evento (Req. 5). |
| `reserva:{usuarioId}:{eventoId}:{setor}` | `String` com `SET NX EX` | 600 s (10 min) | **Reserva temporária** de ingressos com expiração nativa (Req. 6). |
| `ranking:eventos` | `Sorted Set` (ZSET) | Persistente | **Ranking Top 5** alimentado com `ZINCRBY` a cada consulta e lido via `ZREVRANGE` (Req. 7). |
| `limite:reservas:{usuarioId}` | `String` com `INCR` + `EXPIRE` | 60 segundos | **Rate Limiting:** controle de janela de 1 minuto para até 10 reservas por usuário (Req. 8). |
| `pedidos:confirmados` | `Pub/Sub` (Canal) | Mensageria | **Bônus:** transmissão instantânea de novos pedidos confirmados para serviços assinantes. |

---

## 🛡️ Decisões de Arquitetura e Consistência

1. **Invalidação de Cache Dupla (Req. 9):**
   A chave de cache `evento:{id}` é invalidada explicitamente nas operações de `PUT` (edição) e `DELETE` (remoção), bem como imediatamente após a confirmação de um pedido, visto que a contagem de ingressos `vendidos` foi alterada no banco.
2. **Consumo Atômico de Reserva via `GETDEL`:**
   A rota `/pedidos/confirmar` utiliza o comando `GETDEL` do Redis 7. Isso garante que a leitura dos dados da reserva e sua deleção ocorram em um único passo atômico, eliminando condições de corrida onde uma mesma reserva pudesse ser confirmada duas vezes.
3. **Incremento Atômico de Vagas com `$expr` e `arrayFilters`:**
   O incremento de ingressos vendidos é condicionado no próprio filtro da operação `update_one`:
   ```python
   "$and": [
       {"$eq": ["$$s.nome", dados.setor]},
       {"$lte": [{"$add": ["$$s.vendidos", qtd]}, "$$s.capacidade"]}
   ]
   ```
   Se a capacidade do setor for ultrapassada, o MongoDB não modifica nenhum documento (`modified_count == 0`), disparando status `409 Conflict`.
4. **Mecanismo de Compensação (Rollback Lógico):**
   Caso ocorra qualquer erro imprevisto ao persistir o documento do pedido logo após o incremento do setor, uma compensação desfaz o incremento (`$inc: -qtd`) para manter o saldo de ingressos íntegro.

---

## 🔍 Requisito 3 — Índices e Análise do explain()

Os índices são criados automaticamente no startup da aplicação pela função `criar_indices()` em `app/db.py`:

| Coleção | Índice | Tipo | Justificativa |
|:---|:---|:---:|:---|
| `usuarios` | `email` (`uniq_email`) | Único | Garante a unicidade de cadastro por e-mail e previne duplicidades. |
| `eventos` | `categoria` + `data` (`categoria_data`) | Composto | Otimiza a listagem de eventos com filtro por categoria e ordenação cronológica por data. |
| `pedidos` | `usuarioId` (`pedidos_usuario`) | Simples | Acelera buscas de pedidos por usuário e cálculos de histórico. |
| `eventos` | `local.cidade` (`eventos_cidade`) | Simples | Otimiza o filtro geográfico por cidade na busca de eventos. |

### Como Executar o explain()
Com a API ativa, consulte:
```bash
curl "http://localhost:8000/admin/explain?categoria=Show"
```

### Saída Real do explain() (winningPlan)
```json
{
  "stage": "FETCH",
  "inputStage": {
    "stage": "IXSCAN",
    "keyPattern": {
      "categoria": 1,
      "data": 1
    },
    "indexName": "categoria_data",
    "isMultiKey": false,
    "multiKeyPaths": {
      "categoria": [],
      "data": []
    },
    "isUnique": false,
    "isSparse": false,
    "isPartial": false,
    "indexVersion": 2,
    "direction": "forward",
    "indexBounds": {
      "categoria": [
        "[\"Show\", \"Show\"]"
      ],
      "data": [
        "[new Date(1577836800000), new Date(9223372036854775807)]"
      ]
    }
  }
}
```

### Leitura Técnica do Plano de Execução:
1. **`stage: IXSCAN` (Index Scan):** O MongoDB utiliza diretamente a árvore B-Tree do índice composto `categoria_data`, sem inspecionar a coleção documento por documento (`COLLSCAN`).
2. **Bounds Exatos:** O motor aplica o delimitador exato para a categoria (`["Show", "Show"]`) e o intervalo temporal na chave `data`, realizando a ordenação natural dos registros sem alocação de memória para estágio de ordenação (`SORT`).
3. **`stage: FETCH`:** O MongoDB apenas busca do disco os ponteiros de documentos previamente identificados pelo `IXSCAN`, garantindo resposta em sub-milissegundos com consumo mínimo de I/O.

---

## 📹 Roteiro de Demonstração em Vídeo (Até 5 minutos)

Para gravação do vídeo de entrega, execute os passos na ordem a seguir (utilizando o arquivo `ticketflash.http` no VS Code ou Insomnia):

1. **Subir o ambiente:**
   * Execute `docker compose up --build` e mostre os containers `api`, `mongo` e `redis` subindo e ficando saudáveis.
2. **Demonstrar Cache-Aside (`GET /eventos/{id}`):**
   * Chame `GET /eventos/{id}` pela 1ª vez: mostre `"origem": "banco"`.
   * Chame `GET /eventos/{id}` pela 2ª vez: mostre `"origem": "cache"`.
3. **Invalidação de Cache:**
   * Execute `PUT /eventos/{id}` alterando o nome do evento.
   * Chame `GET /eventos/{id}` novamente e mostre que retornou `"origem": "banco"` (cache foi invalidado).
4. **Reserva e Confirmação de Pedido:**
   * Abra o terminal com `docker compose exec api python subscriber.py`.
   * Chame `POST /reservas` criando uma reserva temporária.
   * Chame `POST /pedidos/confirmar`: mostre o pedido confirmado no HTTP e o terminal do assinante Pub/Sub imprimindo a notificação em tempo real.
5. **Tentativa de Confirmar Reserva Expirada/Inexistente:**
   * Chame `POST /pedidos/confirmar` novamente para a mesma reserva já consumida e mostre o erro `HTTP 410 Gone`.
6. **Rate Limiting (429 Too Many Requests):**
   * Dispare 11 requisições seguidas para `POST /reservas` com o mesmo `usuarioId`.
   * Mostre que a 11ª requisição retorna `HTTP 429` com o cabeçalho `Retry-After`.
7. **Ranking e Agregações:**
   * Chame `GET /eventos/ranking` e mostre o Top 5 de visualizações do Redis Sorted Set.
   * Chame `GET /relatorios/faturamento` e mostre os pedidos somados por evento com `$lookup`.
   * Chame `GET /relatorios/ocupacao/{id}` e mostre a taxa de ocupação dos setores calculada via `$unwind` e `$project`.
