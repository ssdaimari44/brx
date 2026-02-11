import { useEffect, useState } from "react";
import axios from "axios";
import CytoscapeComponent from "react-cytoscapejs";
import "./App.css";

const API = "https://knowledgegraphbrx.onrender.com";
const NS = "http://www.semanticweb.org/tsong44/brxgen#";

export default function App() {
  const [classes, setClasses] = useState([]);
  const [properties, setProperties] = useState([]);
  const [individuals, setIndividuals] = useState([]);

  const [selectedClass, setSelectedClass] = useState("");
  const [newName, setNewName] = useState("");

  const [ind1, setInd1] = useState("");
  const [prop, setProp] = useState("");
  const [ind2, setInd2] = useState("");

  const [elements, setElements] = useState([]);
  const [loadedIndividuals, setLoadedIndividuals] = useState(new Set());

  // Question box state
  const [question, setQuestion] = useState("");
  const [queryResults, setQueryResults] = useState(null);
  const [sparqlQuery, setSparqlQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function refreshAll() {
    const classesData = (await axios.get(`${API}/classes`)).data;
    const propertiesData = (await axios.get(`${API}/object-properties`)).data;
    const individualsData = (await axios.get(`${API}/individuals`)).data;
    
    setClasses(classesData);
    setProperties(propertiesData);
    setIndividuals(individualsData);
  }

  useEffect(() => {
    refreshAll();
  }, []);

  async function createIndividual() {
    if (!newName || !selectedClass) return;

    const local = newName.trim().replace(/\s+/g, "_");
    const individualURI = `${NS}${local}`;

    await axios.post(`${API}/create-individual`, null, {
      params: {
        class_uri: selectedClass,
        name: newName
      }
    });

    await refreshAll();
    await addToGraph(individualURI);
    setNewName("");
  }

  async function addToGraph(uri) {
    console.log("Adding to graph:", uri);
    
    try {
      const res = await axios.get(`${API}/graph?uri=${encodeURIComponent(uri)}`);
      
      console.log("Graph data:", res.data);
      
      const newNodes = res.data.nodes.map(n => ({
        data: {
          id: n.id,
          label: n.label || n.id.split("#").pop().split("/").pop()
        }
      }));
      
      const newEdges = res.data.edges.map(e => ({
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label || e.id.split("#").pop().split("/").pop()
        }
      }));
      
      // Merge with existing elements (avoid duplicates)
      setElements(prevElements => {
        const existingNodeIds = new Set(
          prevElements.filter(el => !el.data.source).map(el => el.data.id)
        );
        const existingEdgeIds = new Set(
          prevElements.filter(el => el.data.source).map(el => el.data.id)
        );
        
        const nodesToAdd = newNodes.filter(n => !existingNodeIds.has(n.data.id));
        const edgesToAdd = newEdges.filter(e => !existingEdgeIds.has(e.data.id));
        
        return [...prevElements, ...nodesToAdd, ...edgesToAdd];
      });
      
      setLoadedIndividuals(prev => new Set([...prev, uri]));
      
    } catch (error) {
      console.error("Error loading graph:", error);
    }
  }

  async function createConnection() {
    if (!ind1 || !prop || !ind2) {
      alert("Please select all fields");
      return;
    }
    
    await axios.post(`${API}/create-relation`, null, {
      params: { subject: ind1, predicate: prop, obj: ind2 }
    });
    
    await addToGraph(ind1);
    await addToGraph(ind2);
  }

  function clearGraph() {
    setElements([]);
    setLoadedIndividuals(new Set());
  }

  // async function askQuestion() {
  //   if (!question.trim()) {
  //     alert("Please enter a question");
  //     return;
  //   }

  //   setIsLoading(true);
  //   setQueryResults(null);
  //   setSparqlQuery("");

  //   try {
  //     const response = await axios.post(`${API}/query`, {
  //       question: question
  //     });

  //     setSparqlQuery(response.data.sparql_query || "");
  //     setQueryResults(response.data.results || []);
  //   } catch (error) {
  //     console.error("Error querying knowledge graph:", error);
  //     alert("Error processing query. Please try again.");
  //   } finally {
  //     setIsLoading(false);
  //   }
  // }
    async function askQuestion() {
    if (!question.trim()) {
      alert("Please enter a question");
      return;
    }

    setIsLoading(true);
    setQueryResults(null);
    setSparqlQuery("");

    try {
      // IMPORTANT: Send as query parameter, not body
      const response = await axios.post(`${API}/query`, null, {
        params: { 
          question: question 
        }
      });

      console.log("Response:", response.data); // Debug log

      setSparqlQuery(response.data.sparql_query || "");
      setQueryResults(response.data.results || []);
      
      // Show error if present
      if (response.data.error) {
        alert(`Query Error: ${response.data.error}`);
      }
    } catch (error) {
      console.error("Error querying knowledge graph:", error);
      console.error("Error details:", error.response?.data); // More detailed error
      alert(`Error processing query: ${error.response?.data?.detail || error.message}`);
    } finally {
      setIsLoading(false);
    }
  }

  // function formatResult(result) {
  //   // Format result like: Karan --[enrolledCourse]--> NL
  //   if (result.subject && result.predicate && result.object) {
  //     const subjectName = result.subject.split("#").pop().split("/").pop();
  //     const predicateName = result.predicate.split("#").pop().split("/").pop();
  //     const objectName = result.object.split("#").pop().split("/").pop();
  //     return `${subjectName} --[${predicateName}]--> ${objectName}`;
  //   }
  //   // Fallback for other result formats
  //   return JSON.stringify(result);
  // }
    function formatResult(result) {
    // Helper to extract readable name from URI or return literal value
    const formatValue = (value) => {
      if (!value) return "N/A";
      
      // If it's a URI, extract the local name
      if (value.startsWith("http://") || value.startsWith("https://")) {
        return value.split("#").pop().split("/").pop().replace(/_/g, " ");
      }
      
      // Otherwise it's a literal value, return as-is
      return value;
    };

    // Format result like: Karan --[enrolledCourse]--> NL
    if (result.subject && result.predicate && result.object) {
      const subjectName = formatValue(result.subject);
      const predicateName = formatValue(result.predicate);
      const objectName = formatValue(result.object);
      return `${subjectName} --[${predicateName}]--> ${objectName}`;
    }
    
    // Fallback for other result formats
    return JSON.stringify(result);
  }

  return (
    <div className="app-container">
      <h3 className="section-title">Create Individual</h3>

      <div className="form-row">
        <select 
          className="form-control" 
          value={selectedClass} 
          onChange={e => setSelectedClass(e.target.value)}
        >
          <option value="">Select Class</option>
          {classes.map(c => (
            <option key={c} value={c}>{c.split("#").pop()}</option>
          ))}
        </select>

        <input
          className="form-control"
          placeholder="individual name"
          value={newName}
          onChange={e => setNewName(e.target.value)}
        />

        <button className="btn" onClick={createIndividual}>create</button>
      </div>

      <hr className="divider" />

      <h3 className="section-title">Connect Individuals / Graph</h3>

      <div className="form-row">
        <select 
          className="form-control" 
          value={ind1} 
          onChange={e => setInd1(e.target.value)}
        >
          <option value="">individual name 1</option>
          {individuals.map(i => (
            <option key={i} value={i}>{i.split("#").pop()}</option>
          ))}
        </select>

        <select 
          className="form-control" 
          value={prop} 
          onChange={e => setProp(e.target.value)}
        >
          <option value="">obj property names</option>
          {properties.map(p => (
            <option key={p} value={p}>{p.split("#").pop()}</option>
          ))}
        </select>

        <select 
          className="form-control" 
          value={ind2} 
          onChange={e => setInd2(e.target.value)}
        >
          <option value="">individual name 2</option>
          {individuals.map(i => (
            <option key={i} value={i}>{i.split("#").pop()}</option>
          ))}
        </select>
      </div>

      <div className="form-row">
        <button className="btn" onClick={createConnection}>create connection</button>
        
        <button 
          className="btn btn-secondary" 
          onClick={() => ind1 && addToGraph(ind1)}
        >
          add ind1 to graph
        </button>
        
        <button className="btn btn-secondary" onClick={clearGraph}>
          clear graph
        </button>
      </div>

      <hr className="divider" />

      <div className="main-content">
        {/* Left Panel - Graph */}
        <div className="left-panel">
          <div className="graph-container">
            {elements.length > 0 ? (
              <CytoscapeComponent
                elements={elements}
                style={{ width: "100%", height: "100%" }}
                layout={{ name: "cose", animate: true }}
                stylesheet={[
                  {
                    selector: "node",
                    style: {
                      label: "data(label)",
                      "text-valign": "center",
                      "text-halign": "center",
                      "background-color": "#88a9ce",
                      "border-width": 1,
                      "border-color": "#000000",
                      color: "#361e1e",
                      "font-size": 12,
                      "font-weight": "normal",
                      width: 60,
                      height: 60
                    }
                  },
                  {
                    selector: "edge",
                    style: {
                      label: "data(label)",
                      "curve-style": "bezier",
                      "target-arrow-shape": "triangle",
                      "font-size": 11,
                      "text-rotation": "autorotate",
                      "text-margin-y": -10,
                      width: 2,
                      "line-color": "#bb2e2e",
                      "target-arrow-color": "#ee1a1a"
                    }
                  }
                ]}
              />
            ) : (
              <div className="graph-empty-state">
                No graph data. Create an individual or connection to view.
              </div>
            )}
          </div>
          
          <div className="graph-info">
            Graph contains {elements.filter(e => !e.data.source).length} nodes and {elements.filter(e => e.data.source).length} edges
          </div>
        </div>

        {/* Right Panel - Question Box */}
        <div className="right-panel">
          <div className="question-box">
            <h3 className="section-title">Ask Questions</h3>
            <p style={{ fontSize: '13px', color: '#666', marginBottom: '15px' }}>
              Ask natural language questions about your knowledge graph
            </p>
            
            <textarea
              className="question-input"
              placeholder="e.g., What courses is Karan enrolled in?&#10;Who teaches NL?&#10;Show all students enrolled in AI course"
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyPress={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  askQuestion();
                }
              }}
            />
            
            <button 
              className="btn btn-ask" 
              onClick={askQuestion}
              disabled={isLoading}
            >
              {isLoading ? "Processing..." : "Ask Question"}
            </button>

            {/* Results Section */}
              {(queryResults !== null || isLoading) && (
                <div className="result-container">
                  {isLoading ? (
                    <div className="loading">Processing your question...</div>
                  ) : (
                    <>
                      {queryResults && queryResults.length > 0 ? (
                        <div>
                          <div className="result-header">📋 Answer:</div>
                          {queryResults.map((result, index) => (
                            <div key={index} className="result-item">
                              {formatResult(result)}
                            </div>
                          ))}
                        </div>
                      ) : queryResults && queryResults.length === 0 ? (
                        <div className="no-results">No results found for your question</div>
                      ) : null}
                    </>
                  )}
                </div>
              )}
          </div>
        </div>
      </div>
    </div>
  );
}
