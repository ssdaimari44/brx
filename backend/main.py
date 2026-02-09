from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests

# CHANGE THESE IF NEEDED
SPARQL_ENDPOINT = "http://localhost:3030/brx/sparql"
UPDATE_ENDPOINT = "http://localhost:3030/brx/update"
NS = "http://www.semanticweb.org/tsong44/brxgen#"

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