import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import re

# Use environment variables with fallback
SPARQL_ENDPOINT = os.getenv(
    "SPARQL_ENDPOINT",
    "https://subformative-barer-garret.ngrok-free.dev/dataset/brx/sparql"
)
UPDATE_ENDPOINT = os.getenv(
    "UPDATE_ENDPOINT", 
    "https://subformative-barer-garret.ngrok-free.dev/dataset/brx/update"
)
NS = os.getenv("NAMESPACE", "http://www.semanticweb.org/tsong44/brxgen#")

print("USING SPARQL_ENDPOINT =", SPARQL_ENDPOINT)
print("USING UPDATE_ENDPOINT =", UPDATE_ENDPOINT)

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# import requests
# import re

# # CHANGE THESE IF NEEDED
# SPARQL_ENDPOINT = "https://subformative-barer-garret.ngrok-free.dev/dataset/brx/sparql"
# UPDATE_ENDPOINT = "https://subformative-barer-garret.ngrok-free.dev/dataset/brx/update"
# NS = "http://www.semanticweb.org/tsong44/brxgen#"
# print("USING SPARQL_ENDPOINT =", SPARQL_ENDPOINT)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- helpers -----------------

def sparql_select(query):
    r = requests.get(
        SPARQL_ENDPOINT,
        params={"query": query},
        headers={"Accept": "application/sparql-results+json"}
    )
    r.raise_for_status()
    return r.json()

def sparql_update(query):
    r = requests.post(
        UPDATE_ENDPOINT,
        data=query,
        headers={"Content-Type": "application/sparql-update"}
    )
    r.raise_for_status()
    return {"status": "ok"}

# ----------------- dropdown data -----------------

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Knowledge Graph Backend is running"
    }

@app.get("/classes")
def get_classes():
    q = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?c WHERE { ?c a owl:Class }
    """
    data = sparql_select(q)
    return [r["c"]["value"] for r in data["results"]["bindings"]]

@app.get("/object-properties")
def get_object_properties():
    q = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?p WHERE { ?p a owl:ObjectProperty }
    """
    data = sparql_select(q)
    return [r["p"]["value"] for r in data["results"]["bindings"]]


@app.get("/individuals")
def get_individuals():
    q = f"""
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

    SELECT DISTINCT ?i WHERE {{
      ?i rdf:type ?c .
      FILTER(?c != owl:Class)
      FILTER(?c != owl:ObjectProperty)
      FILTER(?c != owl:Ontology)
    }}
    """
    data = sparql_select(q)
    return [r["i"]["value"] for r in data["results"]["bindings"]]


# ----------------- create individual -----------------

@app.post("/create-individual")
def create_individual(class_uri: str, name: str):
    local = name.strip().replace(" ", "_")
    q = f"""
    PREFIX : <{NS}>
    INSERT {{
      :{local} a <{class_uri}> .
    }}
    WHERE {{
      FILTER NOT EXISTS {{ :{local} a ?x }}
    }}
    """
    return sparql_update(q)

# ----------------- create relation -----------------

@app.post("/create-relation")
def create_relation(subject: str, predicate: str, obj: str):
    q = f"""
    INSERT DATA {{
      <{subject}> <{predicate}> <{obj}> .
    }}
    """
    return sparql_update(q)


# ----------------- natural language query -----------------

@app.post("/query")
def natural_language_query(question: str):
    """
    Generic natural language query handler that works for any question
    """
    question_lower = question.lower().strip()

    stop_words = {
        "what", "where", "who", "when", "why", "how", "is", "are", "was", "were",
        "the", "a", "an", "from", "in", "at", "to", "does", "do", "did", "has", "have",
        "of", "for", "with", "about", "all", "any", "show", "list", "tell", "me"
    }

    words = re.findall(r"\b\w+\b", question_lower)
    entities = [w for w in words if w not in stop_words and len(w) > 1]

    if not entities:
        return {
            "sparql_query": "",
            "results": [],
            "error": "Could not extract any entities from the question."
        }

    # -----------------------------
    # Relationship detection
    # -----------------------------
    relationship_keywords = []

    if any(w in question_lower for w in ["teach", "teaches", "teaching", "taught"]):
        relationship_keywords.append("teach")
    if any(w in question_lower for w in ["enroll", "enrolled", "taking", "course", "courses"]):
        relationship_keywords.append("enroll|course")
    if any(w in question_lower for w in ["work", "works", "job", "office"]):
        relationship_keywords.append("work|office|employ")
    if any(w in question_lower for w in ["manage", "manager", "head"]):
        relationship_keywords.append("manage|head")
    if any(w in question_lower for w in ["member", "belongs", "part of"]):
        relationship_keywords.append("member|belong")

    # -----------------------------
    # Entity filters
    # -----------------------------
    entity_filters = " || ".join(
        [f'CONTAINS(LCASE(STR(?subject)), "{e}")' for e in entities] +
        [f'CONTAINS(LCASE(STR(?object)), "{e}")' for e in entities]
    )

    if relationship_keywords:
        predicate_filter = "FILTER(" + " || ".join(
            [f'REGEX(LCASE(STR(?predicate)), "{kw}")' for kw in relationship_keywords]
        ) + ")"
    else:
        predicate_filter = ""

    # -----------------------------
    # SPARQL query (instance-only)
    # -----------------------------
    sparql_query = f"""
    PREFIX : <{NS}>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>

    SELECT DISTINCT ?subject ?predicate ?object WHERE {{
        ?subject ?predicate ?object .

        FILTER({entity_filters})

        # Remove schema / ontology triples
        FILTER(?predicate NOT IN (
            rdf:type,
            rdfs:subClassOf,
            rdfs:subPropertyOf,
            rdfs:domain,
            rdfs:range,
            owl:equivalentClass,
            owl:equivalentProperty,
            owl:inverseOf,
            owl:disjointWith
        ))

        FILTER(!CONTAINS(STR(?subject), "owl#"))
        FILTER(!CONTAINS(STR(?object), "owl#"))
        FILTER(!CONTAINS(STR(?object), "XMLSchema"))

        FILTER(isIRI(?object) || isLiteral(?object))

        {predicate_filter}
    }}
    LIMIT 50
    """

    try:
        data = sparql_select(sparql_query)

        results = []
        for binding in data["results"]["bindings"]:
            row = {k: v["value"] for k, v in binding.items()}

            # Final guard: skip class-like subjects
            subject_name = row["subject"].split("/")[-1].split("#")[-1]
            if subject_name[0].isupper() and "_" not in subject_name:
                if subject_name.lower() not in entities:
                    continue

            results.append(row)

        return {
            "sparql_query": sparql_query.strip(),
            "results": results
        }

    except Exception as e:
        return {
            "sparql_query": sparql_query.strip(),
            "results": [],
            "error": str(e)
        }


# ----------------- graph -----------------

@app.get("/graph")
def graph(uri: str):
    if uri.endswith("brxgen"):
        return {"nodes": [], "edges": []}

    q = f"""
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT ?p ?o WHERE {{
      <{uri}> ?p ?o .
      FILTER(isIRI(?o))
      FILTER(?o != owl:Ontology)
      FILTER(?p != rdf:type)
    }}
    """
    data = sparql_select(q)

    nodes = [{
        "id": uri,
        "label": uri.split("#")[-1].split("/")[-1]
    }]
    edges = []

    for r in data["results"]["bindings"]:
        o = r["o"]["value"]
        p = r["p"]["value"]

        # Skip owl:Class and other ontology nodes
        if "owl#" in o or "rdf-syntax" in o or "XMLSchema" in o:
            continue

        nodes.append({
            "id": o,
            "label": o.split("#")[-1].split("/")[-1]
        })

        edges.append({
            "id": f"{uri}_{p}_{o}",
            "source": uri,
            "target": o,
            "label": p.split("#")[-1].split("/")[-1]
        })

    return {
        "nodes": list({n["id"]: n for n in nodes}.values()),
        "edges": edges
    }


def sparql_select(query):
    try:
        r = requests.get(
            SPARQL_ENDPOINT,
            params={"query": query},
            headers={"Accept": "application/sparql-results+json"},
            timeout=10  # Add timeout
        )
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        print(f"SPARQL endpoint error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"SPARQL endpoint unavailable: {str(e)}"
        )

