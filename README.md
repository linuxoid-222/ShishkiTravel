# ShishkiTravel
flowchart TB
  user[Пользователь] --> orch[Orchestrator]

  subgraph Agents
    tourist[TouristAgent (RAG-first)]
    legal[LegalAgent (KB-only)]
    responder[ResponderAgent]
    verifier[VerifierAgent]
  end

  subgraph Services
    kb[knowledge_base.py\n(aliases + find_country/city)]
    rag[RAG (Chroma + MiniLM)\nretrieve_advanced(MMR, filters)]
    llm[LLM (gigachat_api)]
    ext[external_apis.py\n(погода, и пр.)]
  end

  orch --> verifier
  orch --> tourist
  orch --> legal

  tourist -->|query+filters| rag
  rag -->|docs (country/city/section)| tourist

  legal -->|visa/laws| kb
  tourist -->|aliases/validation| kb

  tourist --> responder
  legal --> responder
  responder -->|оформление| llm
  responder --> user
