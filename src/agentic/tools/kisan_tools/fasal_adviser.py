from pathlib import Path
import re
from typing import Dict, List, Tuple

from RAW.models.tool import Tool, ToolParam

try:
    import chromadb
    from chromadb.utils import embedding_functions
except Exception:  # pragma: no cover
    chromadb = None
    embedding_functions = None


BASE_DIR = Path(__file__).resolve().parents[4]
KB_DIR = BASE_DIR / "src" / "agentic" / "tools" / "kisan_tools"

DOMAIN_CONFIG = {
    "fasal": {
        "file": KB_DIR / "fasal_adviser.txt",
        "db_dir": BASE_DIR / "vector_store" / "fasal_adviser",
        "collection": "fasal_kb_v1",
        "title": "Fasal Adviser (RAG result):",
    },
    "pest": {
        "file": KB_DIR / "pest_disease.txt",
        "db_dir": BASE_DIR / "vector_store" / "pest_disease",
        "collection": "pest_kb_v1",
        "title": "Pest & Disease Adviser (RAG result):",
    },
    "soil": {
        "file": KB_DIR / "soil_health.txt",
        "db_dir": BASE_DIR / "vector_store" / "soil_health",
        "collection": "soil_health_adviser_kb_v1",
        "title": "Soil Health Adviser (RAG result):",
    },
    "farming": {
        "file": KB_DIR / "farming_tips.txt",
        "db_dir": BASE_DIR / "vector_store" / "farming_tips",
        "collection": "farming_tips_kb_v1",
        "title": "Farming Tips Adviser (RAG result):",
    },
}

CROP_ALIASES: Dict[str, List[str]] = {
    "gehu": ["gehu", "gehun", "wheat"],
    "dhan": ["dhan", "dhaan", "paddy", "rice"],
    "makka": ["makka", "maize", "corn"],
    "tamatar": ["tamatar", "tomato"],
    "pyaz": ["pyaz", "pyaaz", "onion"],
    "kapas": ["kapas", "cotton"],
}
STOP_WORDS = {
    "me", "mein", "ki", "ka", "ke", "aur", "kab", "kya", "kaise", "hai", "hain",
    "karna", "karni", "liye", "se", "ko", "par", "for", "the", "is", "a", "an",
}


def _chunk_text(text: str, chunk_size: int = 700, overlap: int = 80) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _split_sections(raw_text: str) -> List[Tuple[str, str]]:
    lines = raw_text.splitlines()
    sections: List[Tuple[str, str]] = []
    current_title = "general"
    buffer: List[str] = []
    for line in lines:
        stripped = line.strip()
        is_title_line = bool(re.match(r"^=+\s*[^=\s].*[^=\s]\s*=+$", stripped))
        if is_title_line:
            if buffer:
                sections.append((current_title, "\n".join(buffer).strip()))
                buffer = []
            current_title = stripped.strip("= ").strip().lower()
            continue
        buffer.append(line)
    if buffer:
        sections.append((current_title, "\n".join(buffer).strip()))
    return [sec for sec in sections if sec[1]]


def _detect_crop(text: str) -> str:
    lowered = (text or "").lower()
    for crop, aliases in CROP_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            return crop
    return "general"


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9\u0900-\u097F]+", (text or "").lower())
    return [tok for tok in tokens if len(tok) > 2 and tok not in STOP_WORDS]


def _keyword_score(query: str, doc: str) -> float:
    q_terms = set(_tokenize(query))
    if not q_terms:
        return 0.0
    d_terms = set(_tokenize(doc))
    return len(q_terms.intersection(d_terms)) / len(q_terms)


def _prepare_collection(domain: str):
    if chromadb is None or embedding_functions is None:
        raise RuntimeError("RAG dependencies missing. Install: uv add chromadb sentence-transformers")

    config = DOMAIN_CONFIG[domain]
    data_file: Path = config["file"]
    db_dir: Path = config["db_dir"]
    db_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(db_dir))
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = client.get_or_create_collection(
        name=config["collection"],
        embedding_function=embed_fn,
        metadata={"description": f"{domain} knowledge base"},
    )

    if collection.count() == 0:
        if not data_file.exists():
            raise RuntimeError(f"Data file missing: {data_file}")
        raw_text = data_file.read_text(encoding="utf-8").strip()
        if not raw_text:
            raise RuntimeError(f"{data_file.name} is empty. Pehle content add karo.")

        chunks: List[str] = []
        metadatas: List[Dict[str, str]] = []
        for title, section_text in _split_sections(raw_text):
            crop = _detect_crop(title + " " + section_text[:200])
            for piece in _chunk_text(section_text):
                chunks.append(f"{title.upper()}\n{piece}")
                metadatas.append({"source": data_file.name, "crop": crop, "section": title, "domain": domain})
        ids = [f"{domain}_chunk_{i}" for i in range(len(chunks))]
        collection.add(ids=ids, documents=chunks, metadatas=metadatas)
    return collection


def _retrieve_from_domain(domain: str, query: str, top_k: int, session_id: str) -> str:
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return "Sawal likho, tabhi advice de paunga."

    try:
        print(f"[TOOL CALLED] session={session_id} tool={domain}_rag query={cleaned_query}", flush=True)
        collection = _prepare_collection(domain)
        crop_hint = _detect_crop(cleaned_query)
        result = collection.query(query_texts=[cleaned_query], n_results=max(6, int(top_k) * 4))
        docs = (result or {}).get("documents", [[]])[0]
        dists = (result or {}).get("distances", [[]])[0]
        metas = (result or {}).get("metadatas", [[]])[0]
        if not docs:
            return "Is query ke liye relevant info nahi mila."

        scored = []
        for idx, doc in enumerate(docs):
            meta = metas[idx] if idx < len(metas) and isinstance(metas[idx], dict) else {}
            crop_meta = str(meta.get("crop", "general"))
            distance = dists[idx] if idx < len(dists) and dists[idx] is not None else 2.0
            semantic = 1.0 / (1.0 + float(distance))
            lexical = _keyword_score(cleaned_query, doc)
            crop_bonus = 0.1 if crop_hint != "general" and crop_hint == crop_meta else 0.0
            score = (0.65 * semantic) + (0.25 * lexical) + crop_bonus
            scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        final_docs = [doc for _, doc in scored[: max(1, int(top_k))]]
        header = DOMAIN_CONFIG[domain]["title"]
        lines = [header]
        for i, doc in enumerate(final_docs, start=1):
            lines.append(f"{i}. {doc.strip()}")
        return "\n".join(lines)
    except Exception as e:
        return f"{domain.title()} RAG error: {e}"


def get_fasal_advice(query: str, top_k: int = 3, session_id: str = ""):
    return _retrieve_from_domain("fasal", query, top_k, session_id)


def get_pest_advice(query: str, top_k: int = 3, session_id: str = ""):
    return _retrieve_from_domain("pest", query, top_k, session_id)


def get_soil_health_advice(query: str, top_k: int = 3, session_id: str = ""):
    return _retrieve_from_domain("soil", query, top_k, session_id)


def get_farming_tips_advice(query: str, top_k: int = 3, session_id: str = ""):
    return _retrieve_from_domain("farming", query, top_k, session_id)


fasal_adviser_tool = Tool(
    name="get_fasal_advice",
    description="Fasal advice ke liye sirf fasal_adviser.txt vector DB se jankari nikaalta hai.",
    parameters=[ToolParam(name="query", type="string", description="Fasal ka sawal", required=True), ToolParam(name="top_k", type="integer", description="Chunks count", required=False)],
    function=get_fasal_advice,
)

pest_adviser_tool = Tool(
    name="get_pest_advice",
    description="Pest/disease query ke liye sirf pest_disease.txt vector DB use karta hai.",
    parameters=[ToolParam(name="query", type="string", description="Pest ya disease ka sawal", required=True), ToolParam(name="top_k", type="integer", description="Chunks count", required=False)],
    function=get_pest_advice,
)

soil_health_adviser_tool = Tool(
    name="get_soil_health_advice",
    description="Soil health query ke liye sirf soil_health.txt vector DB use karta hai.",
    parameters=[ToolParam(name="query", type="string", description="Mitti/soil health ka sawal", required=True), ToolParam(name="top_k", type="integer", description="Chunks count", required=False)],
    function=get_soil_health_advice,
)

farming_tips_adviser_tool = Tool(
    name="get_farming_tips_advice",
    description="General farming tips query ke liye sirf farming_tips.txt vector DB use karta hai.",
    parameters=[ToolParam(name="query", type="string", description="General kheti tips ka sawal", required=True), ToolParam(name="top_k", type="integer", description="Chunks count", required=False)],
    function=get_farming_tips_advice,
)
