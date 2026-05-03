// src/App.js — Chimera (Arctic Light UI, collapsible sidebar, stable polling)
// KEEP: Narrative Ops unchanged (simple placeholder)

import React, { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Popup, CircleMarker, Polyline } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";


/* ---------------- helpers ---------------- */
const SentBadge = ({ s = 0 }) => {
  if (s > 0.2) return <span className="tag tag-pos">positive {s.toFixed(2)}</span>;
  if (s < -0.2) return <span className="tag tag-neg">negative {s.toFixed(2)}</span>;
  return <span className="tag tag-neu">neutral {Number(s || 0).toFixed(2)}</span>;
};

const b64FromFile = (file) =>
  new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onerror = () => reject(new Error("file read error"));
    r.onloadend = () => {
      const s = String(r.result || "");
      const b64 = s.includes(",") ? s.split(",")[1] : s;
      resolve(b64);
    };
    r.readAsDataURL(file);
  });

/* small pretty time */
const tstr = (ts) =>
  new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

/* ---------------- app ---------------- */
export default function App() {
  // NAV
  const [tab, setTab] = useState("dashboard"); // dashboard|forensics|narrative|opsec
 const [analysisResults, setAnalysisResults] = useState({});
  // SIDEBAR
  const [collapsed, setCollapsed] = useState(false);

  // BACKEND
  const [baseUrl, setBaseUrl] = useState("http://127.0.0.1:8000");
  const [backendOk, setBackendOk] = useState(null); // null|true|false (no flicker)
  const [lastHealth, setLastHealth] = useState("");

  // CONTROLS
  const [mode, setMode] = useState("escalation");
  const [tile, setTile] = useState("Sector-Alpha");
  const [count, setCount] = useState(120);

  // DATA
  const [posts, setPosts] = useState([]);
  const [protest, setProtest] = useState(null); // {score,level,signals,evidence_ids}
  const [coord, setCoord] = useState(null); // {clusters:[]}
  const [highRisk, setHighRisk] = useState([]);
  const [mildRisk, setMildRisk] = useState([]);

  // UI STATE
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  // FORENSICS
  const [ganFile, setGanFile] = useState(null);
  const [ganScore, setGanScore] = useState(null);
  const [ganDetails, setGanDetails] = useState(null);

  const [cameraId, setCameraId] = useState("cam_alpha");
  const [regFiles, setRegFiles] = useState([]);
  const [regResp, setRegResp] = useState(null);
  const [matchFile, setMatchFile] = useState(null);
  const [matchResp, setMatchResp] = useState(null);

  // Derived 30-min window from dataset
  const timeWindow = useMemo(() => {
    if (!posts.length) return null;
    const ts = posts.map((p) => new Date(p.timestamp).getTime());
    const maxT = Math.max(...ts);
    const minT = Math.min(...ts);
    const end = new Date(maxT);
    const start = new Date(Math.max(minT, maxT - 30 * 60 * 1000));
    return { start: start.toISOString(), end: end.toISOString() };
  }, [posts]);

  // Derive safe route from convoy points and highRisk posts
  const { plannedRoute, safeRoute, threatIntersections } = useMemo(() => {
    const waypoints = [
      { lat: 28.7041, lon: 77.1025, name: "Delhi" },
      { lat: 26.9124, lon: 75.7873, name: "Jaipur" },
      { lat: 23.0225, lon: 72.5714, name: "Ahmedabad" },
      { lat: 21.1702, lon: 72.8311, name: "Surat" },
      { lat: 19.0760, lon: 72.8777, name: "Mumbai" },
      { lat: 18.5204, lon: 73.8567, name: "Pune" },
      { lat: 17.3850, lon: 78.4867, name: "Hyderabad" },
      { lat: 12.9716, lon: 77.5946, name: "Bangalore" }
    ];

    const planned = waypoints.map(w => [w.lat, w.lon]);
    const safe = [];
    let hasThreat = false;

    for (let wp of waypoints) {
      let isThreatened = false;
      for (const p of highRisk) {
        const postObj = posts.find(post => post.id === p.id);
        if (postObj?.geo) {
          const dist = Math.sqrt(Math.pow(wp.lat - postObj.geo.lat, 2) + Math.pow(wp.lon - postObj.geo.lon, 2));
          if (dist < 1.0) { // roughly 100km radius threshold
            isThreatened = true;
            break;
          }
        }
      }

      if (isThreatened) {
        hasThreat = true;
        // Bypassing logic: offset the point to simulate a detour
        safe.push([wp.lat, wp.lon + 2.5]);
      } else {
        safe.push([wp.lat, wp.lon]);
      }
    }

    return { 
      plannedRoute: planned, 
      safeRoute: hasThreat ? safe : [], 
      threatIntersections: hasThreat 
    };
  }, [highRisk, posts]);

  /* ---- backend status poll (no flicker) ---- */
  useEffect(() => {
    let cancel = false;
    const check = async () => {
      try {
        const ctrl = new AbortController();
        const id = setTimeout(() => ctrl.abort(), 2500);
        const r = await fetch(`${baseUrl}/health`, { signal: ctrl.signal });
        clearTimeout(id);
        if (cancel) return;
        if (r.ok) {
          const j = await r.json().catch(() => ({}));
          setBackendOk(true);
          setLastHealth(j?.stamp || "");
        } else {
          setBackendOk(false);
        }
      } catch {
        if (!cancel) setBackendOk(false);
      }
    };
    // run once immediately
    check();
    // then poll
    const h = setInterval(check, 5000);
    return () => {
      cancel = true;
      clearInterval(h);
    };
  }, [baseUrl]);

  /* ---------------- API ---------------- */
  const generatePosts = async () => {
    setErr("");
    setLoading(true);
    try {
      const r = await fetch(`${baseUrl}/synthetic/posts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ n: Number(count), tile, mode }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setPosts(data.posts || []);
      // clear derived panels
      setProtest(null);
      setCoord(null);
      setHighRisk([]);
      setMildRisk([]);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  const runProtest = async () => {
    if (!posts.length || !timeWindow)
      return setErr("Generate posts first.");
    setErr("");
    setLoading(true);
    try {
      const r = await fetch(`${baseUrl}/detect/protest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tile,
          start: timeWindow.start,
          end: timeWindow.end,
          posts,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setProtest({
        score: data.score,
        level: data.level,
        signals: data.signals,
        evidence_ids: data.evidence_ids,
      });
      setHighRisk(data.high_risk || []);
      setMildRisk(data.mild_risk || []);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  const runCoordination = async () => {
    if (!posts.length || !timeWindow)
      return setErr("Generate posts first.");
    setErr("");
    setLoading(true);
    try {
      const r = await fetch(`${baseUrl}/detect/coordination`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic_key: "#policyX",
          window_start: timeWindow.start,
          window_end: timeWindow.end,
          posts,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setCoord(data);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };
  const handleScanFeed = async () => {
  try {
    const res = await fetch(baseUrl + "/analyze/auto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        analyst: "Analyst_1",
        posts: posts,
        cluster_title: "Feed Scan",
        create_dossier: true,
        soft_flag: true
      })
    });
    const data = await res.json();
    const resultsMap = {};
    data.items.forEach(item => {
      resultsMap[item.post_id] = item;
    });
    setAnalysisResults(resultsMap);
    if (data.dossier_links) {
      alert("Dossier created! PDF: " + data.dossier_links.pdf_url);
    }
  } catch (err) {
    console.error("Scan error", err);
  }
};


  /* ---- Forensics: GAN ---- */
  const handleGanScore = async () => {
    if (!ganFile) return setErr("Choose an image for GAN scoring.");
    setErr("");
    setLoading(true);
    setGanScore(null);
    setGanDetails(null);
    try {
      const b64 = await b64FromFile(ganFile); // no loops, no recursion
      const r = await fetch(`${baseUrl}/forensics/ganfinger/score`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: { id: "gan_query", b64 } }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setGanScore(data.score ?? 0);
      setGanDetails(data.details || {});
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  /* ---- Forensics: PRNU ---- */
  const handleRegisterCamera = async () => {
    if (regFiles.length < 3) return setErr("Add 3–10 images to register a camera.");
    setErr("");
    setLoading(true);
    setRegResp(null);
    try {
      const images = [];
      for (const f of regFiles) images.push({ id: f.name, b64: await b64FromFile(f) });
      const r = await fetch(`${baseUrl}/forensics/prnu/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ camera_id: cameraId || "camera_unknown", images }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setRegResp(await r.json());
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  const handleMatchCamera = async () => {
    if (!matchFile) return setErr("Choose a query image to match.");
    setErr("");
    setLoading(true);
    setMatchResp(null);
    try {
      const b64 = await b64FromFile(matchFile);
      const r = await fetch(`${baseUrl}/forensics/prnu/match`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ images: [{ id: matchFile.name || "query", b64 }], top_k: 1 }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      setMatchResp((data.results && data.results[0]) || null);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setLoading(false);
    }
  };

  /* ---------------- UI blocks ---------------- */
  const Sidebar = () => {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span>CHIMERA</span>
      </div>

      <nav className="nav">
        <button
          className={`navbtn ${tab === "dashboard" ? "active" : ""}`}
          onClick={() => setTab("dashboard")}
        >
          <span className="ico">📊</span>
          <span>Dashboard</span>
        </button>

        <button
          className={`navbtn ${tab === "forensics" ? "active" : ""}`}
          onClick={() => setTab("forensics")}
        >
          <span className="ico">🧪</span>
          <span>Forensics</span>
        </button>

        <button
          className={`navbtn ${tab === "livemap" ? "active" : ""}`}
          onClick={() => setTab("livemap")}
        >
          <span className="ico">🗺️</span>
          <span>Live Map</span>
        </button>


      </nav>

      <div className="foot">
        <div className="muted small" style={{ marginTop: 10 }}>
          v0.5 • {lastHealth ? `@ ${lastHealth}` : ""}
        </div>
      </div>
    </aside>
  );
};


  const Header = () => (
    <header className="header">
      <div className="title">
        <div>Chimera — Synthetic Info/Media</div>
        <div className="sub">Backend URL</div>
      </div>
      <div className="controls">
        <input className="inp" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
        <div
          className={`badge ${
            backendOk === null ? "unk" : backendOk ? "ok" : "bad"
          }`}
          title={backendOk ? "Backend reachable" : backendOk === false ? "Backend offline" : "Checking"}
        >
          {backendOk === null ? "CHECKING" : backendOk ? "ONLINE" : "OFFLINE"}
        </div>
      </div>
    </header>
  );

  const SocialFeed = ({ posts, coord, protest, timeWindow }) => {
    const coordIds = useMemo(() => {
      const s = new Set();
      if (coord?.clusters) for (const c of coord.clusters) for (const id of c.member_post_ids || []) s.add(id);
      return s;
    }, [coord]);

    const inWin = (ts) => {
      if (!timeWindow) return false;
      const t = new Date(ts).getTime();
      return t >= new Date(timeWindow.start).getTime() && t <= new Date(timeWindow.end).getTime();
    };
    const platform = (p) => p.source || "Synthetic";

    return (
      <div className="card">
        <div className="cardtop">
          <div className="cardtitle">Social Feed</div>
          <div className="muted">{posts.length} posts</div>
        </div>
        <div className="feed">
          {posts.map((p) => {
            const isCluster = coordIds.has(p.id);
            const surge = protest?.level && protest.level !== "baseline" && inWin(p.timestamp);
            const hasImg = (p.media || []).length > 0;
            return (
              <div key={p.id} className="feedItem">
                <div className="feedHead">
                  <div className="muted sm">
                    @{p.user?.id || "user"} · {platform(p)}
                  </div>
                  <div className="muted sm">{tstr(p.timestamp)}</div>
                </div>
                <div className="feedText">{p.text}</div>
                <div className="feedMeta">
                  <div className="metaLeft">
                    {hasImg ? <div className="thumb">🖼</div> : <div className="muted sm">(no image)</div>}
                    <SentBadge s={p.sentiment ?? 0} />
                  </div>
                  <div className="metaRight">
                    {isCluster && <span className="pill warn">⚠ cluster</span>}
                    {surge && <span className="pill hot">🔥 surge</span>}
                    {analysisResults[p.id]?.verdict === "FAKE_DISINFORMATION" && (
                     <span className="flag fake">FAKE</span>
                   )}
{analysisResults[p.id]?.verdict === "SENSITIVE_OPSEC" && (
  <span className="flag opsec">OPSEC</span>
)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  /* ---------------- RENDER ---------------- */
  return (
    <div className="app">
      <Sidebar />
      <main className="main">
        <Header />

        <div className="actionbar">
          <div className="left">
            {tab === "dashboard" && (
              <>
                <select className="inp" value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="baseline">baseline</option>
                  <option value="escalation">escalation</option>
                  <option value="coordination">coordination</option>
                </select>
                <input className="inp" value={tile} onChange={(e) => setTile(e.target.value)} />
                <input className="inp" type="number" value={count} onChange={(e) => setCount(e.target.value)} />
              </>
            )}
          </div>
          <div className="right">
            {tab === "dashboard" && (
              <>
                <button className="btn" onClick={generatePosts} disabled={loading}>Generate</button>
                <button className="btn blue" onClick={runProtest} disabled={loading || !posts.length}>Detect Protest</button>
                <button className="btn purple" onClick={runCoordination} disabled={loading || !posts.length}>Detect Coordination</button>
                <button className="btn red" onClick={handleScanFeed}>Scan Feed (OPSEC/Fake)</button>

              </>
            )}
            {tab === "forensics" && <div className="muted sm">Use tools below</div>}
          </div>
        </div>

        {err && <div className="alert">{String(err)}</div>}

        {tab === "dashboard" && (
          <>
            <div className="grid2">
              <div className="card panel-scroll" style={{ maxHeight: 340 }}>
                <div className="cardtop">
                  <div className="cardtitle">Protest Escalation</div>
                  <div>{protest ? protest.level : ""}</div>
                </div>
                <div className="muted mt8">
                  {protest ? (
                    <>
                      <div>Score: <code>{protest.score}</code></div>
                      <div className="barwrap mt6">
                        <div
                          className={`bar ${
                            protest.score >= 85 ? "bad" : protest.score >= 70 ? "warn" : protest.score >= 40 ? "mid" : "ok"
                          }`}
                          style={{ width: `${Math.min(100, Math.max(0, protest.score))}%` }}
                        />
                      </div>
                      <div className="mt8">Signals:</div>
                      <pre className="pre">{JSON.stringify(protest.signals, null, 2)}</pre>
                    </>
                  ) : "Run detector to see score."}
                </div>
              </div>

              <div className="card panel-scroll" style={{ maxHeight: 340 }}>
                <div className="cardtitle">Coordination / Bot Clusters</div>
                <div className="muted mt8">
                  {coord?.clusters?.length ? (
                    coord.clusters.slice(0, 6).map((c, i) => {
                      const members = (c.member_post_ids || [])
                        .map((id) => posts.find((p) => p.id === id))
                        .filter(Boolean);
                      return (
                        <div key={i} className="cluster">
                          <div>
                            <strong>Cluster {i + 1}</strong> — size {c.size || members.length} — score {c.coordination_score}
                          </div>
                          {c.national_interest_flag && <div className="warntext">⚠ targets national-interest assets</div>}
                          {c.combined_reason && <div className="muted sm">{c.combined_reason}</div>}
                          <div className="mline">
                            {members.map((m) => (
                              <div key={m.id} className="muted sm" style={{ marginTop: 4 }}>
                                <strong>@{m.user?.id}</strong>: {m.text}
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })
                  ) : "No suspicious clusters."}
                </div>
              </div>
            </div>

            <div className="grid2">
              <div className="card">
                <div className="cardtitle">HIGH RISK POSTS</div>
                <div className="listbox">
                  {highRisk.length ? (
                    highRisk.map((p) => (
                      <div key={p.id} className="listitem">
                        <div className="lihead">@{p.id}</div>
                        <div className="litxt">{p.text}</div>
                        <div className="muted sm mt6"><strong>Reason:</strong> {p.reason}</div>
                      </div>
                    ))
                  ) : (
                    <div className="muted sm">No high-risk posts.</div>
                  )}
                </div>
              </div>

              <div className="card">
                <div className="cardtitle">MILD RISK POSTS</div>
                <div className="listbox">
                  {mildRisk.length ? (
                    mildRisk.map((p) => (
                      <div key={p.id} className="listitem">
                        <div className="lihead">@{p.id}</div>
                        <div className="litxt">{p.text}</div>
                        <div className="muted sm mt6"><strong>Reason:</strong> {p.reason}</div>
                      </div>
                    ))
                  ) : (
                    <div className="muted sm">No mild-risk posts.</div>
                  )}
                </div>
              </div>
            </div>

            <div className="card">
              <div className="cardtitle">Dataset</div>
              <div className="muted mt8">
                {posts.length} posts (mode: <strong>{mode}</strong>, tile: <strong>{tile}</strong>)
              </div>
              <details className="mt8">
                <summary className="summary">Preview first 3 (raw)</summary>
                <pre className="pre">{JSON.stringify(posts.slice(0, 3), null, 2)}</pre>
              </details>
            </div>

            <SocialFeed posts={posts} protest={protest} coord={coord} timeWindow={timeWindow} />
          </>
        )}

        {tab === "forensics" && (
          <>
            {/* GAN */}
            <div className="card">
              <div className="cardtop">
                <div className="cardtitle">GAN Deepfake Scan</div>
                <div className="muted sm">POST: <code>/forensics/ganfinger/score</code></div>
              </div>
              <div className="row mt8">
                <input type="file" accept="image/*" onChange={(e) => setGanFile(e.target.files?.[0] || null)} />
                <button className="btn orange" onClick={handleGanScore} disabled={loading || !ganFile}>Score Image</button>
              </div>
              {ganScore !== null && (
                <div className="mt10">
                  <div className="row space">
                    <div>Score: <strong>{ganScore}</strong> / 100</div>
                    <div className="muted sm">
                      {ganScore >= 70 ? "Suspicious / Likely Synthetic" : ganScore >= 40 ? "Borderline" : "Likely Natural"}
                    </div>
                  </div>
                  <div className="barwrap mt6">
                    <div className={`bar ${ganScore >= 70 ? "bad" : ganScore >= 40 ? "warn" : "ok"}`} style={{ width: `${ganScore}%` }} />
                  </div>
                  {ganDetails && (
                    <div className="mt8">
                      <div><strong>Gridiness:</strong> {ganDetails.gridiness}</div>
                      <div><strong>Channel Anomaly:</strong> {ganDetails.channel_anomaly}</div>
                      <div><strong>Blockiness:</strong> {ganDetails.blockiness}</div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* PRNU */}
            <div className="card">
              <div className="cardtop">
                <div className="cardtitle">PRNU Camera Fingerprinting</div>
                <div className="muted sm">
                  POST: <code>/forensics/prnu/register</code> • <code>/forensics/prnu/match</code>
                </div>
              </div>

              <div className="grid2 mt8">
                <div>
                  <div className="cardsubtitle">1) Register Camera</div>
                  <div className="row mt8">
                    <input className="inp" value={cameraId} onChange={(e) => setCameraId(e.target.value)} placeholder="camera_id" />
                  </div>
                  <div className="row mt8">
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      onChange={(e) => setRegFiles(Array.from(e.target.files || []))}
                    />
                    <button
                      className="btn green"
                      onClick={handleRegisterCamera}
                      disabled={loading || regFiles.length < 3}
                    >
                      Register ({regFiles.length})
                    </button>
                  </div>
                  {regResp && (
                    <div className="muted mt8">
                      <div><strong>Status:</strong> {regResp.status}</div>
                      <div><strong>Camera:</strong> {regResp.camera_id}</div>
                      <div><strong>Strength:</strong> {regResp.strength}</div>
                    </div>
                  )}
                  <div className="muted sm mt6">Tip: 5–10 images from the SAME device work best.</div>
                </div>

                <div>
                  <div className="cardsubtitle">2) Match Query Image</div>
                  <div className="row mt8">
                    <input type="file" accept="image/*" onChange={(e) => setMatchFile(e.target.files?.[0] || null)} />
                    <button className="btn blue" onClick={handleMatchCamera} disabled={loading || !matchFile}>Match Camera</button>
                  </div>
                  {matchResp && (
                    <div className="muted mt8">
                      <div><strong>Image:</strong> {matchResp.image_id}</div>
                      <div><strong>Best Camera:</strong> {matchResp.best_camera || "Unknown"}</div>
                      <div><strong>ZNCC:</strong> {matchResp.zncc}</div>
                      <div><strong>PCE:</strong> {matchResp.pce}</div>
                    </div>
                  )}
                  <div className="muted sm mt6">Matches cameras registered in this session.</div>
                </div>
              </div>
            </div>
          </>
        )}

        {tab === "livemap" && (
          <div className="card" style={{ height: '700px', padding: 0, overflow: 'hidden' }}>
            <MapContainer center={[20.5937, 78.9629]} zoom={5} style={{ height: '100%', width: '100%' }}>
              <TileLayer
                className="deep-blue-map"
                url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                attribution='&copy; CARTO'
              />
              {plannedRoute.length > 0 && (
                <Polyline 
                  positions={plannedRoute} 
                  pathOptions={{ 
                    color: threatIntersections ? '#ef4444' : '#3b82f6', 
                    weight: 3, 
                    dashArray: threatIntersections ? '5, 10' : null 
                  }} 
                />
              )}
              {safeRoute.length > 0 && (
                <Polyline 
                  positions={safeRoute} 
                  pathOptions={{ color: '#10b981', weight: 4 }} 
                />
              )}
              {posts.map(p => (
                <CircleMarker 
                  key={p.id} 
                  center={[p.geo.lat, p.geo.lon]} 
                  radius={6} 
                  fillColor="#3b82f6" 
                  color="#3b82f6" 
                  weight={1} 
                  fillOpacity={0.6}
                >
                  <Popup>
                    <div style={{color: '#000'}}>
                      <strong>@{p.user?.id}</strong><br/>
                      {p.text}
                    </div>
                  </Popup>
                </CircleMarker>
              ))}
              {highRisk.map(p => {
                const postObj = posts.find(post => post.id === p.id);
                if (!postObj?.geo?.lat) return null;
                return (
                  <CircleMarker 
                    key={`threat-${p.id}`} 
                    center={[postObj.geo.lat, postObj.geo.lon]} 
                    radius={30} 
                    fillColor="#ef4444" 
                    color="#ef4444" 
                    weight={2} 
                    fillOpacity={0.3}
                  >
                    <Popup>
                      <div style={{color: '#000'}}>
                        <strong>⚠ THREAT ZONE</strong><br/>
                        {p.reason}
                      </div>
                    </Popup>
                  </CircleMarker>
                );
              })}
            </MapContainer>
          </div>
        )}


      </main>
    </div>
  );
}

