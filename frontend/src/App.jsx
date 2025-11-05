
// frontend/src/App.jsx
import React, { useRef, useState } from "react";
import jsPDF from "jspdf";
import html2canvas from "html2canvas";
import {
  PieChart,
  Pie,
  Sector,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer
} from "recharts";

const COLORS = [
  "#22c55e", "#60a5fa", "#f97316", "#a78bfa", "#f43f5e", "#fb923c",
  "#06b6d4", "#f59e0b", "#84cc16", "#7c3aed"
];

export default function App() {
  const fileRef = useRef();
  const reportRef = useRef();
  const jobRefs = useRef({});
  const [fileName, setFileName] = useState("");
  const [loading, setLoading] = useState(false);
  const [parsed, setParsed] = useState(null);
  const [error, setError] = useState(null);
  const [activeIndex, setActiveIndex] = useState(null);

  // NEW: openai key state
  const [openaiKey, setOpenaiKey] = useState("");

  function onFileChange(e) {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    if (f.type !== "application/pdf") {
      setError("Please select a PDF file");
      return;
    }
    setError(null);
    setFileName(f.name);
    setParsed(null);
  }

  async function submit() {
    const input = fileRef.current && fileRef.current.files && fileRef.current.files[0];
    if (!input) {
      setError("Please choose a PDF first");
      return;
    }
    if (!openaiKey || openaiKey.trim().length === 0) {
      setError("Please enter your OpenAI API key");
      return;
    }

    setError(null);
    setLoading(true);
    setParsed(null);
    setActiveIndex(null);

    try {
      const fd = new FormData();
      fd.append("pdf_doc", input, input.name);

      const res = await fetch("http://127.0.0.1:8000/api/process", {
        method: "POST",
        body: fd,
        headers: {
          // send user key to backend
          "x-openai-key": openaiKey.trim()
        }
      });
      const j = await res.json();
      let result = j.result ?? j;

      if (result && typeof result === "object" && result.raw_output) {
        if (typeof result.raw_output === "string") {
          try { result = JSON.parse(result.raw_output); } catch { result = { raw_text: result.raw_output }; }
        } else { result = result.raw_output; }
      }

      if (typeof result === "string") {
        try { result = JSON.parse(result); } catch (e) {
          setError("Backend returned text instead of JSON: " + result.slice(0, 200));
          setLoading(false);
          return;
        }
      }

      if (!result || typeof result !== "object") {
        setError("Unexpected backend response");
        setLoading(false);
        return;
      }

      const normalized = normalizeResult(result);
      setParsed(normalized);
    } catch (e) {
      setError(e.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  function normalizeResult(r) {
    const full_name = r.full_name ?? r.fullName ?? r.name ?? null;
    const email = r.email ?? r.email_id ?? null;
    const linkedin = r.linkedin
      ? typeof r.linkedin === "string" && !r.linkedin.startsWith("http")
        ? "https://" + r.linkedin
        : r.linkedin
      : null;
    const github = r.github ?? null;
    const employment_raw = r.employment_details ?? r.employment ?? r.experience ?? [];
    const employment = Array.isArray(employment_raw) ? employment_raw : [];

    let technical_list = [];
    if (r.technical_skills && typeof r.technical_skills === "object") {
      for (const k of Object.keys(r.technical_skills)) {
        const v = r.technical_skills[k];
        if (Array.isArray(v)) technical_list.push(...v);
        else if (typeof v === "string") technical_list.push(v);
      }
    } else if (Array.isArray(r.technical_skills)) technical_list = r.technical_skills;

    const soft_skills = Array.isArray(r.soft_skills) ? r.soft_skills
      : typeof r.soft_skills === "string" ? r.soft_skills.split(/[,;\n]/).map(s=>s.trim()).filter(Boolean) : [];
    const education = Array.isArray(r.education) ? r.education : r.education ? [r.education] : [];
    const languages = Array.isArray(r.languages) ? r.languages : r.languages ? [r.languages] : [];
    const certifications = Array.isArray(r.certifications) ? r.certifications : r.certifications ? [r.certifications] : [];
    const phone = r.phone ?? r.mobile ?? null;

    const experience_analysis = r.experience_analysis ?? null;
    const assessment = r.assessment ?? null;

    return {
      full_name,
      email,
      phone,
      linkedin,
      github,
      education,
      technical_skills: technical_list,
      soft_skills,
      employment,
      languages,
      certifications,
      experience_analysis,
      assessment,
      raw: r
    };
  }

  function downloadJSON() {
    if (!parsed) return;
    const blob = new Blob([JSON.stringify(parsed, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const fname = (parsed.full_name || "resume").replace(/\s+/g, "_").toLowerCase();
    a.download = `${fname}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function downloadPDF() {
    if (!parsed) return;
    const el = reportRef.current;
    if (!el) return;
    try {
      const canvas = await html2canvas(el, { scale: 2, useCORS: true, backgroundColor: "#0f172a" });
      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF({
        orientation: canvas.width > canvas.height ? "landscape" : "portrait",
        unit: "px",
        format: [canvas.width, canvas.height]
      });
      pdf.addImage(imgData, "PNG", 0, 0, canvas.width, canvas.height);
      const fname = (parsed.full_name || "resume-report").replace(/\s+/g, "-").toLowerCase();
      pdf.save(`${fname}.pdf`);
    } catch (e) {
      setError("PDF generation failed: " + (e.message || e));
    }
  }

  function buildPieData() {
    const ea = parsed?.experience_analysis;
    if (!ea || !Array.isArray(ea.per_job) || ea.per_job.length === 0) return [];
    const data = ea.per_job.map((j, idx) => {
      const months = (j.duration_months != null && !isNaN(j.duration_months)) ? Number(j.duration_months) : null;
      return {
        name: `${j.job_title || j.company || "Job " + (idx+1)}`,
        value: months || 1,
        idx,
        company: j.company,
        title: j.job_title,
        duration_human: j.duration_human || j.duration || null
      };
    }).filter(Boolean);
    if (data.every(d => !d.value)) {
      return data.map(d => ({ ...d, value: 1 }));
    }
    return data;
  }

  const onPieEnter = (_, index) => setActiveIndex(index);
  const onPieLeave = () => setActiveIndex(null);

  function onPieClick(data, index) {
    const idx = data?.payload?.idx ?? index;
    const jobEl = jobRefs.current[idx];
    if (jobEl && jobEl.scrollIntoView) {
      jobEl.scrollIntoView({ behavior: "smooth", block: "center" });
      jobEl.classList.add("ring-2", "ring-indigo-500");
      setTimeout(()=> jobEl.classList.remove("ring-2", "ring-indigo-500"), 1500);
    }
  }

  function getJobRef(idx) {
    if (!jobRefs.current[idx]) jobRefs.current[idx] = null;
    return (el) => { jobRefs.current[idx] = el; };
  }

  function renderJobDuration(job) {
    if (!job) return null;
    const human = job.duration_human || job.duration || job.duration_human_readable || null;
    const start = job.start_date_parsed || job.start_date || job.start_date_raw || job.start || null;
    const end = job.end_date_parsed || job.end_date || job.end_date_raw || job.end || null;
    return (
      <div className="text-sm text-gray-400">
        {(start || end) && <div>{start ? start : ""}{start && end ? " — " + end : end ? " — " + end : ""}</div>}
        {human && <div className="mt-1">{human}</div>}
      </div>
    );
  }

  function ScoreBar({score}) {
    const s = Number(score) || 0;
    const pct = Math.max(0, Math.min(100, s));
    let color = "bg-green-500";
    if (pct < 50) color = "bg-red-500";
    else if (pct < 70) color = "bg-yellow-500";
    return (
      <div className="w-40">
        <div className="text-sm text-gray-300 mb-1">Overall score: {pct}</div>
        <div className="w-full bg-gray-700 rounded h-3">
          <div className={`${color} h-3 rounded`} style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  }

  const renderActiveShape = (props) => {
    const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill, payload, value } = props;
    return (
      <g>
        <text x={cx} y={cy} dy={-6} textAnchor="middle" fill="#fff" fontWeight={700}>{payload.name}</text>
        <text x={cx} y={cy} dy={18} textAnchor="middle" fill="#aaa">{payload.duration_human ?? `${value} mo`}</text>
        <Sector
          cx={cx}
          cy={cy}
          innerRadius={innerRadius}
          outerRadius={outerRadius + 8}
          startAngle={startAngle}
          endAngle={endAngle}
          fill={fill}
        />
      </g>
    );
  };

  const pieData = parsed ? buildPieData() : [];

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <div className="max-w-6xl mx-auto">

        {/* TOOL TITLE */}
        <div className="mb-6">
          <h1 className="text-3xl font-extrabold text-white">CV Insights and Candidate Assessment Tool</h1>
          <p className="text-gray-400 mt-1">Upload a resume (PDF) → Paste your OpenAI key → Process</p>
        </div>

        {/* ----- Aligned upload + key + buttons block ----- */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          {/* File Upload (styled) */}
          <label className="inline-flex items-center bg-white/10 px-4 py-2 rounded cursor-pointer">
            <input ref={fileRef} type="file" accept=".pdf" className="hidden" onChange={onFileChange} />
            <span className="bg-white/90 text-blue-600 px-3 py-1 rounded-full mr-3">Choose File</span>
            <span className="text-gray-300 text-sm">{fileName || "No file chosen"}</span>
          </label>

          {/* API Key - aligned with buttons (no helper text) */}
          <input
            type="password"
            placeholder="Paste your OpenAI API key (sk-...)"
            value={openaiKey}
            onChange={(e)=>setOpenaiKey(e.target.value)}
            className="w-80 px-4 py-2 text-sm rounded-full bg-gray-800 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />

          {/* Process / Clear */}
          <button
            onClick={submit}
            disabled={loading || !fileRef.current?.files?.length || !openaiKey}
            className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2 rounded-full disabled:opacity-60"
          >
            {loading ? "Processing…" : "Process"}
          </button>

          <button
            onClick={() => { fileRef.current.value = null; setFileName(""); setParsed(null); setError(null); setOpenaiKey(""); }}
            className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-full"
          >
            Clear
          </button>

          <div className="ml-auto flex gap-2">
            <button onClick={downloadJSON} disabled={!parsed} className="bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-2 rounded-full disabled:opacity-60">Download JSON</button>
            <button onClick={downloadPDF} disabled={!parsed} className="bg-green-600 hover:bg-green-500 text-white px-5 py-2 rounded-full disabled:opacity-60">Download PDF</button>
          </div>
        </div>

        {error && <div className="text-red-400 mb-4">{error}</div>}

        <div ref={reportRef}>
          {!parsed && <div className="p-6 bg-black/40 rounded text-gray-400">No parsed report yet. Upload a PDF and click Process (with your OpenAI key).</div>}

          {parsed && (
            <div className="bg-gradient-to-r from-gray-800/60 to-gray-900/60 p-6 rounded text-gray-100">
              {/* Header */}
              <div className="flex justify-between items-start mb-6">
                <div>
                  <div className="text-2xl font-bold">{parsed.full_name || "Name not found"}</div>
                </div>
                <div className="text-sm text-gray-300 text-right">
                  {parsed.email && <div>✉️ {parsed.email}</div>}
                  {parsed.phone && <div>📱 {parsed.phone}</div>}
                  {parsed.linkedin && <div><a href={parsed.linkedin} target="_blank" rel="noreferrer" className="underline">{parsed.linkedin}</a></div>}
                </div>
              </div>

              {/* Education */}
              <section className="mb-6">
                <h3 className="text-lg font-semibold text-white mb-3">Education</h3>
                {parsed.education && parsed.education.length > 0 ? (
                  <ul className="list-disc list-inside text-gray-300">
                    {parsed.education.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                ) : <div className="text-gray-400">No education found</div>}
              </section>

              {/* Skills */}
              <section className="mb-6">
                <h3 className="text-lg font-semibold text-white mb-3">Skills</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 bg-black/30 rounded">
                    <div className="text-sm text-gray-300 mb-2">Technical</div>
                    {parsed.technical_skills && parsed.technical_skills.length > 0 ? (
                      <div className="flex flex-wrap gap-2">{parsed.technical_skills.map((s,i)=>(<span key={i} className="bg-gray-700/40 px-3 py-1 rounded-full text-sm">{s}</span>))}</div>
                    ) : <div className="text-gray-400">No technical skills found</div>}
                  </div>

                  <div className="p-4 bg-black/30 rounded">
                    <div className="text-sm text-gray-300 mb-2">Soft</div>
                    {parsed.soft_skills && parsed.soft_skills.length > 0 ? (
                      <div className="flex flex-wrap gap-2">{parsed.soft_skills.map((s,i)=>(<span key={i} className="bg-gray-700/40 px-3 py-1 rounded-full text-sm">{s}</span>))}</div>
                    ) : <div className="text-gray-400">No soft skills found</div>}
                  </div>
                </div>
              </section>

              {/* Experience + Chart/Assessment area */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                  <section className="mb-6">
                    <div className="flex justify-between items-center mb-3">
                      <h3 className="text-lg font-semibold text-white">Work Experience</h3>
                      {parsed.experience_analysis && parsed.experience_analysis.total_human_readable && (
                        <div className="text-sm text-gray-300">Total experience: <span className="font-medium text-white">{parsed.experience_analysis.total_human_readable}</span></div>
                      )}
                    </div>

                    {parsed.employment && parsed.employment.length > 0 ? (
                      <div className="space-y-4">
                        {parsed.employment.map((job, idx) => {
                          let analysisJob = null;
                          if (parsed.experience_analysis && Array.isArray(parsed.experience_analysis.per_job)) {
                            analysisJob = parsed.experience_analysis.per_job.find(j =>
                              (j.company && job.company && j.company.trim().toLowerCase() === job.company.trim().toLowerCase()) ||
                              (j.job_title && job.job_title && j.job_title.trim().toLowerCase() === job.job_title.trim().toLowerCase())
                            ) ?? null;
                          }
                          const title = job.job_title || job.title || "";
                          const company = job.company || "";
                          const responsibilities = job.responsibilities || [];

                          return (
                            <div key={idx} ref={getJobRef(idx)} className="p-4 bg-black/30 rounded" style={{scrollMarginTop: 120}}>
                              <div className="flex justify-between">
                                <div>
                                  <div className="text-md font-semibold text-white">{title || "Title"}</div>
                                  <div className="text-sm text-gray-300">{company}</div>
                                </div>
                                <div>
                                  {analysisJob ? renderJobDuration(analysisJob) : renderJobDuration(job)}
                                </div>
                              </div>

                              {responsibilities && responsibilities.length > 0 && (
                                <ul className="list-disc list-inside mt-3 text-gray-300 text-sm">
                                  {responsibilities.map((r,i)=>(<li key={i}>{r}</li>))}
                                </ul>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ) : <div className="text-gray-400">No work experience found</div>}
                  </section>
                </div>

                <div className="lg:col-span-1 space-y-4">
                  <div className="p-4 bg-black/30 rounded">
                    <div className="flex items-center justify-between mb-3">
                      <div className="text-sm text-gray-300 font-medium">Experience Distribution</div>
                      <div className="text-xs text-gray-400">Hover or click slices</div>
                    </div>

                    {pieData && pieData.length > 0 ? (
                      <div style={{ width: "100%", height: 260 }}>
                        <ResponsiveContainer>
                          <PieChart>
                            <Pie
                              data={pieData}
                              dataKey="value"
                              nameKey="name"
                              cx="50%"
                              cy="50%"
                              innerRadius={40}
                              outerRadius={70}
                              fill="#8884d8"
                              onMouseEnter={onPieEnter}
                              onMouseLeave={onPieLeave}
                              onClick={onPieClick}
                              activeIndex={activeIndex}
                              activeShape={renderActiveShape}
                            >
                              {pieData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} cursor="pointer" />
                              ))}
                            </Pie>
                            <Tooltip formatter={(value, name, props) => [`${value} months`, name]} />
                            <Legend verticalAlign="bottom" layout="vertical" align="center" payload={pieData.map((d, i) => ({ value: `${d.name} (${d.duration_human ?? d.value + " mo"})`, type: "square", id: d.name }))} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    ) : (
                      <div className="text-gray-400">No duration data available for chart</div>
                    )}
                  </div>

                  <div className="p-4 bg-black/30 rounded">
                    <div className="flex justify-between items-start mb-3">
                      <div className="text-sm text-gray-300 font-medium">AI Assessment</div>
                      {parsed.assessment && parsed.assessment.overall_score !== undefined && <ScoreBar score={parsed.assessment.overall_score} />}
                    </div>

                    {parsed.assessment ? (
                      <div className="space-y-3 text-sm text-gray-300">
                        <div>
                          <div className="text-xs text-gray-400 mb-1 font-medium">Strengths</div>
                          {parsed.assessment.strengths && parsed.assessment.strengths.length > 0 ? (
                            <ul className="list-disc list-inside">{parsed.assessment.strengths.map((s,i)=>(<li key={i}>{s}</li>))}</ul>
                          ) : <div className="text-gray-400">None identified</div>}
                        </div>

                        <div>
                          <div className="text-xs text-gray-400 mb-1 font-medium">Weaknesses</div>
                          {parsed.assessment.weaknesses && parsed.assessment.weaknesses.length > 0 ? (
                            <ul className="list-disc list-inside">{parsed.assessment.weaknesses.map((s,i)=>(<li key={i}>{s}</li>))}</ul>
                          ) : <div className="text-gray-400">None identified</div>}
                        </div>

                        <div>
                          <div className="text-xs text-gray-400 mb-1 font-medium">Recommendations</div>
                          {parsed.assessment.recommendations && parsed.assessment.recommendations.length > 0 ? (
                            <ul className="list-disc list-inside">{parsed.assessment.recommendations.map((s,i)=>(<li key={i}>{s}</li>))}</ul>
                          ) : <div className="text-gray-400">No recommendations</div>}
                        </div>
                      </div>
                    ) : <div className="text-gray-400">No assessment available</div>}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
                <div className="p-4 bg-black/30 rounded">
                  <div className="text-sm text-gray-300 mb-2">Languages</div>
                  {parsed.languages && parsed.languages.length > 0 ? (
                    <div className="flex flex-wrap gap-2">{parsed.languages.map((l,i)=>(<span key={i} className="bg-gray-700/40 px-3 py-1 rounded-full text-sm">{l}</span>))}</div>
                  ) : <div className="text-gray-400">No languages found</div>}
                </div>

                <div className="p-4 bg-black/30 rounded">
                  <div className="text-sm text-gray-300 mb-2">Certifications</div>
                  {parsed.certifications && parsed.certifications.length > 0 ? (
                    <ul className="list-disc list-inside text-gray-300 text-sm">{parsed.certifications.map((c,i)=>(<li key={i}>{c}</li>))}</ul>
                  ) : <div className="text-gray-400">No certifications found</div>}
                </div>
              </div>

            </div>
          )}
        </div>

      </div>
    </div>
  );
}
