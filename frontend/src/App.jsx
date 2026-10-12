import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";
const USER_ID = 2;

const EMPTY_TASK = { title: "", category: "Academic", difficulty: 5, importance: 5, estimated_duration: 60, deadline: "", goal_id: "" };
const EMPTY_GOAL = { name: "", category: "Academic", importance: 7, target_date: "" };

function localDateKey() {
  const d = new Date();
  const offset = d.getTimezoneOffset();

  return new Date(
    d.getTime() - offset * 60000
  ).toISOString().slice(0, 10);
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) throw new Error(await response.text() || `Request failed: ${response.status}`);
  return response.json();
}

function App() {
  const [section, setSection] = useState("dashboard");
  const [user, setUser] = useState(null);
  const [goals, setGoals] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [dailyState, setDailyState] = useState(null);
  const [states, setStates] = useState([]);
  const [schedule, setSchedule] = useState([]);
  const [outcomes, setOutcomes] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [planning, setPlanning] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [profile, setProfile] = useState({ name: "", available_hours: 8, normal_sleep_hours: 8, preferred_start_time: "08:00" });
  const [goalForm, setGoalForm] = useState(EMPTY_GOAL);
  const [taskForm, setTaskForm] = useState(EMPTY_TASK);
  const [stateForm, setStateForm] = useState({ available_hours: 8, sleep_hours: 7, energy: 7, focus: 7, workload: 5, exercise_minutes: 30 });
  const [selectedTask, setSelectedTask] = useState(null);
  const [outcomeForm, setOutcomeForm] = useState({ actual: "", completed: true, rating: "", notes: "" });
  const [assistantQuestion, setAssistantQuestion] = useState("");
  const [assistantAnswer, setAssistantAnswer] = useState("");
  const [assistantMode, setAssistantMode] = useState("");
  const [mlEvaluation, setMlEvaluation] = useState(null);
  const [mlEvaluationLoading, setMlEvaluationLoading] = useState(false);
  const [mlEvaluationError, setMlEvaluationError] = useState("");

  const today = new Date().toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
  const pending = useMemo(() => tasks.filter(t => t.status === "pending"), [tasks]);
  const completed = useMemo(() => tasks.filter(t => t.status === "completed"), [tasks]);
  const scheduled = useMemo(() => schedule.filter(s => s.scheduled), [schedule]);
  const plannedMinutes = scheduled.reduce((sum, x) => sum + Number(x.predicted_duration || 0), 0);
  const capacityHours = Number(dailyState?.available_hours ?? profile?.available_hours ?? 8);
  const capacityMinutes = capacityHours * 60;
  const freeMinutes = Math.max(capacityMinutes - plannedMinutes, 0);
  const taskCompletion = tasks.length ? Math.round(completed.length / tasks.length * 100) : 0;
  const avgProbability = scheduled.length ? Math.round(scheduled.reduce((s, x) => s + Number(x.completion_probability), 0) / scheduled.length * 100) : 0;

  async function refresh({ regenerate = true } = {}) {
    const [users, goalsData, tasksData, statesData, outcomesData, analyticsData, predictionData] = await Promise.all([
      api("/users/"), api("/goals/"), api("/tasks/"), api(`/daily-state/?user_id=${USER_ID}`), api(`/outcomes/user/${USER_ID}`), api(`/analytics/user/${USER_ID}`), api(`/analytics/predictions/${USER_ID}`)
    ]);
    const current = users.find(u => u.id === USER_ID);
    const userGoals = goalsData.filter(g => g.user_id === USER_ID);
    const userTasks = tasksData.filter(t => t.user_id === USER_ID);
    const currentStates = statesData.filter(s => s.user_id === USER_ID);
    const todayKey = localDateKey();
    const todayState = currentStates.find(s => s.date === todayKey);
    setUser(current);
    setGoals(userGoals);
    setTasks(userTasks);
    setStates(currentStates);
    setDailyState(todayState || null);
    setOutcomes(outcomesData);
    setAnalytics(analyticsData);
    setPredictions(predictionData);
    if (current) {
      setProfile({ name: current.name || "", available_hours: current.available_hours ?? 8, normal_sleep_hours: current.normal_sleep_hours ?? 8, preferred_start_time: current.preferred_start_time || "08:00" });
    }
    setStateForm({
      available_hours: todayState?.available_hours ?? current?.available_hours ?? 8,
      sleep_hours: todayState?.sleep_hours ?? 7,
      energy: todayState?.energy ?? 7,
      focus: todayState?.focus ?? 7,
      workload: todayState?.workload ?? 5,
      exercise_minutes: todayState?.exercise_minutes ?? 30,
    });
    if (regenerate) {
      const plan = await api(`/planner/generate/${USER_ID}?available_hours=${Number(todayState?.available_hours ?? current?.available_hours ?? 8)}`);
      setSchedule(plan);
      setMlEvaluation(null);
    }
  }

  useEffect(() => {
    (async () => {
      try { await refresh(); }
      catch (e) { console.error(e); setError("APLO could not connect. Start FastAPI on port 8000."); }
      finally { setLoading(false); }
    })();
  }, []);

  useEffect(() => {
    if (section !== "evaluation" || mlEvaluation) return;
    let active = true;
    setMlEvaluationLoading(true);
    setMlEvaluationError("");
    api(`/ml/evaluation/${USER_ID}`)
      .then(data => { if (active) setMlEvaluation(data); })
      .catch(e => { if (active) setMlEvaluationError(e.message || "Could not load ML evaluation data."); })
      .finally(() => { if (active) setMlEvaluationLoading(false); });
    return () => { active = false; };
  }, [section, mlEvaluation]);

  function notify(text) { setMessage(text); setTimeout(() => setMessage(""), 4200); }
  function fail(text) { setError(text); setTimeout(() => setError(""), 5000); }
  function minutes(value) { const n = Math.max(0, Math.round(Number(value || 0))); const h = Math.floor(n / 60); const m = n % 60; return h ? `${h}h ${m}m` : `${m}m`; }
  function pct(value) { return `${Math.round(Number(value || 0) * 100)}%`; }
  function deadline(value) { if (!value) return "No deadline"; return new Date(value).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); }
  function goalById(id) { return goals.find(g => g.id === id); }

  async function saveProfile(e) {
    e.preventDefault(); setSaving(true);
    try { await api(`/users/${USER_ID}`, { method: "PUT", body: JSON.stringify({ ...profile, available_hours: Number(profile.available_hours), normal_sleep_hours: Number(profile.normal_sleep_hours) }) }); await refresh(); notify("Profile saved. Planning constraints updated."); }
    catch { fail("Could not save profile."); } finally { setSaving(false); }
  }

  async function createGoal(e) {
    e.preventDefault(); if (!goalForm.name.trim()) return fail("Enter a goal name."); setSaving(true);
    try { await api("/goals/", { method: "POST", body: JSON.stringify({ user_id: USER_ID, ...goalForm, importance: Number(goalForm.importance), target_date: goalForm.target_date || null, progress: 0 }) }); setGoalForm(EMPTY_GOAL); await refresh(); notify("Goal added to the optimization context."); }
    catch (e) {
      let detail = e.message || "Unknown error";
      try {
        const response = JSON.parse(detail);
        detail = Array.isArray(response.detail)
          ? response.detail.map(issue => issue.msg).join("; ")
          : response.detail || detail;
      } catch {}
      fail(`Could not create goal: ${detail}`);
    } finally { setSaving(false); }
  }

  async function createTask(e) {
    e.preventDefault(); if (!taskForm.title.trim()) return fail("Enter a task title."); setSaving(true);
    try {
      await api("/tasks/", { method: "POST", body: JSON.stringify({ user_id: USER_ID, goal_id: taskForm.goal_id ? Number(taskForm.goal_id) : null, title: taskForm.title.trim(), category: taskForm.category, difficulty: Number(taskForm.difficulty), importance: Number(taskForm.importance), estimated_duration: Number(taskForm.estimated_duration), deadline: taskForm.deadline || null }) });
    } catch (e) {
      let detail = e.message || "Unknown error";
      try {
        const response = JSON.parse(detail);
        detail = Array.isArray(response.detail)
          ? response.detail.map(issue => issue.msg).join("; ")
          : response.detail || detail;
      } catch {}
      fail(`Could not create task: ${detail}`);
      setSaving(false);
      return;
    }

    setTaskForm(EMPTY_TASK);
    try {
      await refresh();
      notify("Task added. Re-optimize to place it in the plan.");
    } catch (e) {
      fail(`Task created, but the list could not refresh: ${e.message || "Unknown error"}`);
    } finally { setSaving(false); }
  }
  
  async function deleteTask(taskId) {
    if (!window.confirm("Remove this task? APLO will regenerate today's plan without it.")) return;
    setSaving(true);
    try {
      await api(`/tasks/${taskId}?user_id=${USER_ID}`, { method: "DELETE" });
    } catch (e) {
      let detail = e.message || "Unknown error";
      try {
        const response = JSON.parse(detail);
        detail = Array.isArray(response.detail)
          ? response.detail.map(issue => issue.msg).join("; ")
          : response.detail || detail;
      } catch {}
      fail(`Could not remove task: ${detail}`);
      setSaving(false);
      return;
    }
  
    setTasks(current => current.filter(task => task.id !== taskId));
    setSchedule(current => current.filter(item => item.task_id !== taskId));
    try {
      await refresh();
      notify("Task removed. Today's plan was regenerated.");
    } catch (e) {
      fail(`Task removed, but the plan could not refresh: ${e.message || "Unknown error"}`);
    } finally { setSaving(false); }
  }

  async function saveState(e) {
    e.preventDefault(); setSaving(true);
    try {
      const todayKey = localDateKey();
      const savedState = await api("/daily-state/", { method: "POST", body: JSON.stringify({ user_id: USER_ID, date: todayKey, available_hours: Number(stateForm.available_hours), sleep_hours: Number(stateForm.sleep_hours), energy: Number(stateForm.energy), focus: Number(stateForm.focus), workload: Number(stateForm.workload), exercise_minutes: Number(stateForm.exercise_minutes) }) });
      setDailyState(savedState);
      setStateForm({
        available_hours: savedState.available_hours,
        sleep_hours: savedState.sleep_hours,
        energy: savedState.energy,
        focus: savedState.focus,
        workload: savedState.workload,
        exercise_minutes: savedState.exercise_minutes,
      });
      const hours = Number(savedState.available_hours);
      const newPlan = await api(`/planner/generate/${USER_ID}?available_hours=${hours}`);
      setSchedule(newPlan);
      setMlEvaluation(null);
      await refresh({ regenerate: false });
      notify("Today's state and planning capacity were saved. APLO re-optimized immediately.");
    }
    catch { fail("Could not save today's state."); } finally { setSaving(false); }
  }

  async function reoptimize() {
    setPlanning(true);
    try { const hours = dailyState?.available_hours ?? profile?.available_hours ?? 8; const plan = await api(`/planner/generate/${USER_ID}?available_hours=${Number(hours)}`); setSchedule(plan); setMlEvaluation(null); await refresh({ regenerate: false }); notify("Plan re-optimized from the latest tasks, goals, predictions and today's state."); }
    catch { fail("Could not re-optimize the plan."); } finally { setPlanning(false); }
  }

  function openOutcome(item) {
    setSelectedTask(item);
    setOutcomeForm({ actual: String(Math.round(item.predicted_duration)), completed: true, rating: "", notes: "" });
  }

  async function submitOutcome(e) {
    e.preventDefault(); if (!selectedTask || Number(outcomeForm.actual) <= 0) return fail("Enter the actual duration."); setSaving(true);
    try {
      const params = new URLSearchParams({ actual_duration: Number(outcomeForm.actual), completed: outcomeForm.completed });
      if (outcomeForm.rating) params.set("user_rating", Number(outcomeForm.rating));
      if (outcomeForm.notes.trim()) params.set("notes", outcomeForm.notes.trim());
      await api(`/outcomes/${selectedTask.task_id}?${params.toString()}`, { method: "POST" });
      setMlEvaluation(null);
      setSelectedTask(null); await refresh(); notify("Outcome recorded. APLO now has observed behavior for future predictions.");
    } catch { fail("Could not record outcome."); } finally { setSaving(false); }
  }

  async function askAssistant(question = assistantQuestion) {
    if (!question.trim()) return;
    setAssistantQuestion(question); setAssistantAnswer("");
    try { const data = await api(`/assistant/${USER_ID}`, { method: "POST", body: JSON.stringify({ question }) }); setAssistantAnswer(data.answer); setAssistantMode(data.mode); }
    catch { fail("Assistant is unavailable."); }
  }

  if (loading) return <div className="loading"><div className="logo-mark">A</div><h2>Initializing APLO</h2><p>Loading goals, behavior history and optimization state…</p></div>;

  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><div className="logo-mark">A</div><div><b>APLO</b><span>Adaptive Life Optimizer</span></div></div>
      <nav>{[["dashboard","Dashboard","⌂"],["profile","Profile","◉"],["goals","Goals","◆"],["tasks","Tasks","✓"],["state","Life State","◌"],["history","History","◷"],["evaluation","ML Evaluation","▥"],["assistant","AI Assistant","✦"]].map(([id,label,icon]) => <button key={id} className={section === id ? "nav active" : "nav"} onClick={() => setSection(id)}><i>{icon}</i>{label}</button>)}</nav>
      <div className="engine"><span></span><div><b>Optimization engine</b><small>online · adaptive baseline</small></div></div>
    </aside>

    <main className="main">
      <header className="topbar">
        <div><small>PERSONAL OPTIMIZATION SYSTEM</small><h1>{section === "dashboard" ? <>Good day, <em>{user?.name || "User"}</em></> : <>{sectionTitle(section)} <em>{user?.name || "User"}</em></>}</h1><p>{today}</p></div>
        <div className="top-actions"><div className="capacity"><b>{minutes(plannedMinutes)}</b><span>planned / {minutes(capacityMinutes)}</span></div><button className="primary" onClick={reoptimize} disabled={planning}>{planning ? "Optimizing…" : "✦ Re-optimize"}</button></div>
      </header>

      {message && <div className="toast success">✓ {message}<button onClick={() => setMessage("")}>×</button></div>}
      {error && <div className="toast error">⚠ {error}<button onClick={() => setError("")}>×</button></div>}

      {section === "dashboard" && <Dashboard {...{ state: dailyState, schedule, pending, completed, plannedMinutes, freeMinutes, taskCompletion, avgProbability, minutes, pct, deadline, openOutcome, setSection, outcomes, analytics, goals, goalById, reoptimize }} />}
      {section === "profile" && <Profile profile={profile} setProfile={setProfile} saveProfile={saveProfile} saving={saving} />}
      {section === "goals" && <Goals goals={goals} goalForm={goalForm} setGoalForm={setGoalForm} createGoal={createGoal} saving={saving} goalById={goalById} tasks={tasks} />}
      {section === "tasks" && <Tasks tasks={tasks} goals={goals} taskForm={taskForm} setTaskForm={setTaskForm} createTask={createTask} deleteTask={deleteTask} saving={saving} schedule={schedule} minutes={minutes} deadline={deadline} />}
      {section === "state" && <LifeState state={dailyState} states={states} stateForm={stateForm} setStateForm={setStateForm} saveState={saveState} saving={saving} />}
      {section === "history" && <History outcomes={outcomes} states={states} analytics={analytics} predictions={predictions} minutes={minutes} />}
      {section === "evaluation" && <MLEvaluationPage data={mlEvaluation} loading={mlEvaluationLoading} error={mlEvaluationError} />}
      {section === "assistant" && <Assistant question={assistantQuestion} setQuestion={setAssistantQuestion} answer={assistantAnswer} mode={assistantMode} ask={askAssistant} />}

      {selectedTask && <OutcomeModal task={selectedTask} form={outcomeForm} setForm={setOutcomeForm} onClose={() => setSelectedTask(null)} onSubmit={submitOutcome} saving={saving} minutes={minutes} />}
    </main>
  </div>;
}

function sectionTitle(section) { return ({ profile: "Profile ·", goals: "Goals ·", tasks: "Tasks ·", state: "Life State ·", history: "Learning History ·", evaluation: "ML Evaluation ·", assistant: "APLO Assistant ·" }[section] || "APLO ·"); }

function Dashboard({ state, schedule, pending, completed, plannedMinutes, freeMinutes, taskCompletion, avgProbability, minutes, pct, deadline, openOutcome, setSection, outcomes, analytics, goals, goalById, reoptimize }) {
  return <>
    <section className="hero panel">
      <div><small>ADAPTIVE PLANNING</small><h2>Your day, optimized around <em>reality.</em></h2><p>APLO combines goals, deadlines, behavioral predictions and today's life state to decide what fits into your available capacity.</p><div className="hero-actions"><button className="primary" onClick={() => setSection("state")}>Update life state</button><button className="secondary" onClick={() => setSection("tasks")}>Manage tasks</button></div></div>
      <div className="score-orb"><b>{avgProbability || 0}%</b><span>average completion<br/>probability</span></div>
    </section>

    <div className="metrics"><Metric label="Planned time" value={minutes(plannedMinutes)} note="predicted workload"/><Metric label="Free capacity" value={minutes(freeMinutes)} note="remaining today"/><Metric label="Task completion" value={`${taskCompletion}%`} note={`${completed.length} completed · ${pending.length} pending`}/><Metric label="Today's energy" value={state ? `${state.energy}/10` : "—"} note={state ? "from life state" : "not recorded"}/></div>

    <div className="grid-main">
      <section className="panel plan">
        <div className="panel-head"><div><small>OPTIMIZED PLAN</small><h3>Today's schedule</h3></div><button className="tiny-link" onClick={reoptimize}>recalculate ↻</button></div>
        {schedule.length ? schedule.map((item, i) => <div className={`schedule ${item.scheduled ? "" : "unscheduled"}`} key={`${item.task_id}-${i}`}>
          <div className="time"><b>{item.scheduled_start || "—"}</b><span>{item.scheduled_end || ""}</span></div><div className="step">{i + 1}</div><div className="schedule-main"><div className="task-title"><b>{item.title}</b>{item.goal_name && <span className="goal-chip">{item.goal_name}</span>}</div><span className="sub">Estimate {minutes(item.estimated_duration)} → <strong>{minutes(item.predicted_duration)}</strong> predicted · {deadline(item.deadline)}</span><div className="tags"><span>Priority {item.priority}</span><span>{pct(item.completion_probability)} likely</span><span>D{item.difficulty}</span><span>I{item.importance}</span></div><details><summary>Why this prediction?</summary><p>{item.duration_explanation}</p><p>{item.priority_explanation}</p></details></div>{item.scheduled ? <button className="record" onClick={() => openOutcome(item)}>Record outcome</button> : <span className="blocked">{item.reason}</span>}</div>) : <Empty text="No pending work. Add a task to generate a plan."/>}
      </section>

      <aside className="side-column">
        <section className="panel state-card"><div className="panel-head"><div><small>CURRENT STATE</small><h3>What APLO sees</h3></div></div>{state ? <>{<Bar label="Energy" value={state.energy}/>}<Bar label="Focus" value={state.focus}/><Bar label="Workload" value={state.workload} inverse/><Bar label="Sleep" value={Math.min(10, Number(state.sleep_hours) * 1.25)}/></> : <Empty text="Save today's state to improve adaptation."/>}</section>
        <section className="panel goals-mini"><div className="panel-head"><div><small>OBJECTIVES</small><h3>Goal progress</h3></div><button className="tiny-link" onClick={() => setSection("goals")}>view all</button></div>{goals.slice(0, 3).map(g => <div className="goal-mini" key={g.id}><div><b>{g.name}</b><span>{g.importance}/10 importance</span></div><strong>{Math.round(Number(g.progress || 0))}%</strong><div className="progress"><i style={{ width: `${Math.min(100, Number(g.progress || 0))}%` }}/></div></div>)}</section>
        <section className="panel learning"><small>LEARNING LOOP</small><h3>{outcomes.length} observed outcomes</h3><p>{analytics?.mean_absolute_error_minutes != null ? `Average prediction error: ${analytics.mean_absolute_error_minutes} minutes.` : "Record outcomes so APLO can learn your real task duration."}</p><button className="secondary" onClick={() => setSection("history")}>Review behavior history →</button></section>
      </aside>
    </div>
  </>;
}

function MLEvaluationPage({ data, loading, error }) {
  const chartRows = (data?.prediction_history || []).filter(row =>
    row.predicted_duration != null && row.actual_duration != null
  );
  const duration = data?.duration || {};
  const completion = data?.completion || {};
  const feedback = data?.feedback || {};
  const formatMetric = (value, digits = 3) => value == null ? "—" : Number(value).toFixed(digits);
  const formatPercent = value => value == null ? "—" : `${(Number(value) * 100).toFixed(1)}%`;
  const formatMinutes = value => value == null ? "—" : `${Number(value).toFixed(Number.isInteger(Number(value)) ? 0 : 2)} min`;
  const formatError = value => value == null ? "—" : `${Number(value) > 0 ? "+" : ""}${Number(value).toFixed(2)} min`;

  return <Section title="ML Evaluation" subtitle="Model performance and behavioral prediction evidence." eyebrow="MODEL EVIDENCE">
    {loading && <div className="panel evaluation-message">Loading stored model and outcome evidence…</div>}
    {error && <div className="panel evaluation-message error-text">Could not load evaluation data: {error}</div>}
    {data && <>
      <div className="evaluation-section-label"><small>MODEL EVALUATION DATA</small></div>
      <section className="panel evaluation-status">
        <div className="evaluation-status-item"><small>MODEL</small><strong>{data.model_version || "not trained"}</strong></div>
        <div className="evaluation-status-item"><small>TRAINING SAMPLES</small><strong>{data.training_samples ?? 0}</strong></div>
        <div className="evaluation-status-item"><small>PREDICTION TARGETS</small><strong>Duration · Completion probability</strong></div>
        <div className="evaluation-status-item"><small>LAST TRAINED</small><strong>{data.trained_at ? new Date(data.trained_at).toLocaleString() : "—"}</strong></div>
        <div className="evaluation-status-item"><small>HELD-OUT EVALUATION SAMPLES</small><strong>{data.evaluation_samples ?? 0}</strong></div>
      </section>

      <div className="evaluation-metric-grid">
        <section className="panel evaluation-metric-group">
          <div className="panel-head"><div><small>REGRESSION</small><h3>Duration Prediction</h3></div></div>
          <div className="evaluation-metrics">
            <Metric label="MAE" value={duration.mae == null ? "—" : `${formatMetric(duration.mae, 2)} min`} note="held-out mean absolute error" />
            <Metric label="R²" value={formatMetric(duration.r2)} note="held-out coefficient of determination" />
          </div>
        </section>
        <section className="panel evaluation-metric-group">
          <div className="panel-head"><div><small>CLASSIFICATION</small><h3>Completion Prediction</h3></div></div>
          <div className="evaluation-metrics">
            <Metric label="Accuracy" value={formatPercent(completion.accuracy)} note="held-out predictions" />
            <Metric label="Precision" value={formatPercent(completion.precision)} note="completed-class precision" />
            <Metric label="Recall" value={formatPercent(completion.recall)} note="completed-class recall" />
            <Metric label="F1" value={formatPercent(completion.f1)} note="completed-class F1" />
          </div>
        </section>
      </div>

      <div className="evaluation-section-label"><small>USER BEHAVIOR DATA</small></div>
      <section className="panel evaluation-chart-panel">
        <div className="panel-head"><div><small>OUTCOME EVIDENCE</small><h3>Actual vs predicted duration</h3></div><span className="badge">{chartRows.length} matched</span></div>
        <ActualVsPredictedChart rows={chartRows} />
      </section>

      <section className="panel evaluation-history-panel">
        <div className="panel-head"><div><small>STORED MODEL OUTPUTS</small><h3>Prediction history</h3></div><span className="badge">{data.prediction_count ?? 0} predictions</span></div>
        <div className="evaluation-table-wrap">
          <table className="evaluation-table">
            <thead><tr><th>Task</th><th>Predicted</th><th>Actual</th><th>Error</th><th>Completion probability</th><th>Outcome</th><th>Model</th></tr></thead>
            <tbody>
              {data.prediction_history?.map(row => <tr key={row.prediction_id}>
                <td>{row.task_title}<small>Task #{row.task_id}</small></td>
                <td>{formatMinutes(row.predicted_duration)}</td>
                <td>{formatMinutes(row.actual_duration)}</td>
                <td>{formatError(row.duration_error)}</td>
                <td>{formatPercent(row.completion_probability)}</td>
                <td>{row.completed == null ? "No outcome" : row.completed ? "Completed" : "Incomplete"}</td>
                <td>{row.model_version || "—"}</td>
              </tr>)}
              {!data.prediction_history?.length && <tr><td colSpan="7" className="evaluation-empty">No stored predictions yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel evaluation-feedback-panel">
        <div className="panel-head"><div><small>ADAPTATION LOOP</small><h3>Feedback available for future training</h3></div></div>
        <div className="feedback-flow" aria-label="Prediction, user action, outcome, prediction error, future training data">
          <span>Prediction</span><i>↓</i><span>User action</span><i>↓</i><span>Outcome</span><i>↓</i><span>Prediction error</span><i>↓</i><span>Future training data</span>
        </div>
        <div className="feedback-counts">
          <Metric label="Predictions recorded" value={data.prediction_count ?? 0} note="stored scheduler outputs" />
          <Metric label="Outcomes recorded" value={feedback.outcomes_recorded ?? 0} note="task session outcomes" />
          <Metric label="Measured durations" value={feedback.measured_duration_outcomes ?? 0} note="outcomes with actual duration" />
          <Metric label="Completed outcomes" value={feedback.completed_outcomes ?? 0} note="recorded as completed" />
        </div>
        <p className="evaluation-note">These outcomes are available as future training data. The current code does not automatically retrain the deployed model.</p>
      </section>

      <p className="evaluation-note evaluation-demo-note">Current model metrics include seeded/demo training history. Personalization quality should be evaluated again as real user behavior accumulates. The Maths — Algebra Practice outcome used the rounded predicted duration during demo testing; it is not an independent real-world duration validation.</p>
    </>}
  </Section>;
}

function ActualVsPredictedChart({ rows }) {
  if (!rows.length) return <p className="evaluation-message">Not enough completed prediction data yet.</p>;
  const max = Math.max(10, ...rows.flatMap(row => [Number(row.predicted_duration), Number(row.actual_duration)]));
  const ceiling = Math.ceil(max / 10) * 10;
  const left = 58;
  const top = 18;
  const width = 540;
  const height = 210;
  const point = value => ({ x: left + (Number(value) / ceiling) * width, y: top + height - (Number(value) / ceiling) * height });
  const tickStep = ceiling <= 80 ? 20 : Math.ceil(ceiling / 4 / 10) * 10;
  const ticks = Array.from({ length: Math.floor(ceiling / tickStep) + 1 }, (_, index) => index * tickStep);

  return <div className="evaluation-chart-wrap">
    <svg viewBox="0 0 640 280" role="img" aria-label="Scatter plot comparing stored predicted durations with matched actual durations">
      {ticks.map(tick => {
        const position = point(tick);
        return <g key={tick}>
          <line x1={left} y1={position.y} x2={left + width} y2={position.y} className="evaluation-chart-grid" />
          <line x1={position.x} y1={top} x2={position.x} y2={top + height} className="evaluation-chart-grid" />
          <text x={left - 10} y={position.y + 4} textAnchor="end" className="evaluation-chart-label">{tick}</text>
          <text x={position.x} y={top + height + 20} textAnchor="middle" className="evaluation-chart-label">{tick}</text>
        </g>;
      })}
      <line x1={left} y1={top + height} x2={left + width} y2={top} className="evaluation-chart-reference" />
      <text x={left + width / 2} y="274" textAnchor="middle" className="evaluation-chart-label">Predicted duration (min)</text>
      <text x="14" y={top + height / 2} textAnchor="middle" className="evaluation-chart-label" transform={`rotate(-90 14 ${top + height / 2})`}>Actual duration (min)</text>
      {rows.map(row => {
        const coordinates = point(row.predicted_duration);
        const actualCoordinates = point(row.actual_duration);
        return <circle key={row.prediction_id} cx={coordinates.x} cy={actualCoordinates.y} r="5" className="evaluation-chart-point">
          <title>{`${row.task_title}: predicted ${row.predicted_duration} min, actual ${row.actual_duration} min`}</title>
        </circle>;
      })}
    </svg>
    <p className="chart-legend"><span /> Stored prediction/outcome pairs only; diagonal indicates equal predicted and actual durations.</p>
  </div>;
}

function Profile({ profile, setProfile, saveProfile, saving }) { return <Section title="Profile" eyebrow="INPUT LAYER" subtitle="These personal constraints define the capacity APLO is allowed to schedule."><form className="form panel"><div className="form-grid"><Field label="Name"><input value={profile.name} onChange={e => setProfile({...profile,name:e.target.value})}/></Field><Field label="Default available hours"><input type="number" min="0" max="24" step="0.5" value={profile.available_hours} onChange={e => setProfile({...profile,available_hours:e.target.value})}/></Field><Field label="Normal sleep hours"><input type="number" min="0" max="14" step="0.5" value={profile.normal_sleep_hours} onChange={e => setProfile({...profile,normal_sleep_hours:e.target.value})}/></Field><Field label="Preferred start time"><input type="time" value={profile.preferred_start_time} onChange={e => setProfile({...profile,preferred_start_time:e.target.value})}/></Field></div><button className="primary" disabled={saving}>{saving ? "Saving…" : "Save profile"}</button></form><div className="explain panel"><b>What this changes</b><p>Available hours becomes a hard planning capacity. Preferred start time shifts the generated schedule. Sleep target is stored as personal context; today's actual sleep comes from Life State.</p></div></Section>; }

function Goals({ goals, goalForm, setGoalForm, createGoal, saving, tasks }) { return <Section title="Goals" subtitle="Long-term objectives give individual tasks their optimization context." eyebrow="OBJECTIVE LAYER"><form className="form panel" onSubmit={createGoal}><div className="form-grid"><Field label="Goal name"><input placeholder="e.g. Master DSA" value={goalForm.name} onChange={e=>setGoalForm({...goalForm,name:e.target.value})}/></Field><Field label="Category"><select value={goalForm.category} onChange={e=>setGoalForm({...goalForm,category:e.target.value})}><option>Academic</option><option>Career</option><option>Health</option><option>Personal</option><option>Social</option></select></Field><Field label="Importance 1–10"><input type="number" min="1" max="10" value={goalForm.importance} onChange={e=>setGoalForm({...goalForm,importance:e.target.value})}/></Field><Field label="Target date"><input type="date" value={goalForm.target_date} onChange={e=>setGoalForm({...goalForm,target_date:e.target.value})}/></Field></div><button type="submit" className="primary" disabled={saving}>{saving ? "Adding…" : "+ Add goal"}</button></form><div className="cards-list">{goals.map(g => { const linked=tasks.filter(t=>t.goal_id===g.id); const done=linked.filter(t=>t.status==="completed").length; return <div className="goal-card panel" key={g.id}><div className="goal-head"><div><span className="goal-icon">◆</span><div><h3>{g.name}</h3><p>{g.category} · importance {g.importance}/10 · target {g.target_date || "open"}</p></div></div><strong>{Math.round(Number(g.progress||0))}%</strong></div><div className="progress large"><i style={{width:`${Math.min(100,Number(g.progress||0))}%`}}/></div><div className="goal-meta"><span>{done}/{linked.length} linked tasks completed</span><span>{linked.length ? "Task-weighted progress" : "No linked tasks yet"}</span></div>{linked.length>0&&<div className="linked-list">{linked.map(t=><span key={t.id} className={t.status}>{t.status === "completed" ? "✓" : "○"} {t.title}</span>)}</div>}</div>})}{!goals.length&&<Empty text="Create a goal to give your tasks long-term context."/>}</div></Section>; }

function Tasks({ tasks, goals, taskForm, setTaskForm, createTask, deleteTask, saving, schedule, minutes, deadline }) {
  return <Section title="Tasks" subtitle="APLO predicts duration and completion probability before allocating time." eyebrow="WORK LAYER">
    <form className="form panel" onSubmit={createTask}>
      <div className="form-grid wide">
        <Field label="Task title" wide><input placeholder="e.g. Solve 10 binary tree problems" value={taskForm.title} onChange={e=>setTaskForm({...taskForm,title:e.target.value})}/></Field>
        <Field label="Goal"><select value={taskForm.goal_id} onChange={e=>setTaskForm({...taskForm,goal_id:e.target.value})}><option value="">No linked goal</option>{goals.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></Field>
        <Field label="Category"><select value={taskForm.category} onChange={e=>setTaskForm({...taskForm,category:e.target.value})}><option>Academic</option><option>Career</option><option>Health</option><option>Personal</option><option>Social</option></select></Field>
        <Field label="Difficulty 1–10"><input type="number" min="1" max="10" value={taskForm.difficulty} onChange={e=>setTaskForm({...taskForm,difficulty:e.target.value})}/></Field>
        <Field label="Importance 1–10"><input type="number" min="1" max="10" value={taskForm.importance} onChange={e=>setTaskForm({...taskForm,importance:e.target.value})}/></Field>
        <Field label="Your estimate (minutes)"><input type="number" min="15" step="5" value={taskForm.estimated_duration} onChange={e=>setTaskForm({...taskForm,estimated_duration:e.target.value})}/></Field>
        <Field label="Deadline"><input type="datetime-local" value={taskForm.deadline} onChange={e=>setTaskForm({...taskForm,deadline:e.target.value})}/></Field>
      </div>
      <button type="submit" className="primary" disabled={saving}>{saving ? "Adding…" : "+ Add task"}</button>
    </form>
    <div className="table panel">
      <div className="table-head"><span>Task</span><span>Goal</span><span>Priority inputs</span><span>Deadline</span><span>Status</span></div>
      {tasks.map(t=><div className="table-row" key={t.id}>
        <div><b>{t.title}</b><small>{t.category} · {t.estimated_duration || "—"} min estimate</small></div>
        <span>{goals.find(g=>g.id===t.goal_id)?.name || "—"}</span>
        <span>D{t.difficulty} · I{t.importance}</span>
        <span>{deadline(t.deadline)}</span>
        <span className="task-actions"><em className={t.status}>{t.status}</em>{t.status === "pending" && <button type="button" className="task-remove" disabled={saving} aria-label={`Remove ${t.title}`} onClick={()=>deleteTask(t.id)}>Remove</button>}</span>
      </div>)}
    </div>
    <div className="explain panel"><b>Estimate vs prediction</b><p>Your estimate is an input, not the final schedule duration. APLO adjusts it using difficulty and today's state, then blends toward historical observed durations when enough behavior exists. Expand “Why this prediction?” on the Dashboard to see the exact calculation.</p></div>
  </Section>;
}

function LifeState({ state, states, stateForm, setStateForm, saveState, saving }) { return <Section title="Today's Life State" subtitle="One record per calendar day. Updating today replaces today's record; previous days remain as history." eyebrow="BEHAVIORAL CONTEXT"><form className="form panel" onSubmit={saveState}><div className="slider-grid"><Slider label="Available time" value={stateForm.available_hours} min="0" max="24" step="0.5" suffix="h" set={v=>setStateForm({...stateForm,available_hours:v})}/><Slider label="Sleep" value={stateForm.sleep_hours} min="0" max="12" step="0.5" suffix="h" set={v=>setStateForm({...stateForm,sleep_hours:v})}/><Slider label="Energy" value={stateForm.energy} min="1" max="10" step="1" suffix="/10" set={v=>setStateForm({...stateForm,energy:v})}/><Slider label="Focus" value={stateForm.focus} min="1" max="10" step="1" suffix="/10" set={v=>setStateForm({...stateForm,focus:v})}/><Slider label="Workload" value={stateForm.workload} min="1" max="10" step="1" suffix="/10" set={v=>setStateForm({...stateForm,workload:v})}/><Slider label="Exercise" value={stateForm.exercise_minutes} min="0" max="180" step="5" suffix="m" set={v=>setStateForm({...stateForm,exercise_minutes:v})}/></div><button type="submit" className="primary" disabled={saving}>{saving ? "Saving…" : "Save today's state & re-optimize"}</button></form><div className="panel history-panel"><div className="panel-head"><div><small>DAILY RECORDS</small><h3>Recent life-state history</h3></div><span className="badge">{states.length} records</span></div>{states.slice(0,7).map(s=><div className="day-row" key={s.id}><b>{new Date(`${s.date}T00:00:00`).toLocaleDateString([], {weekday:"short",month:"short",day:"numeric"})}</b><span>Sleep {s.sleep_hours}h</span><span>Energy {s.energy}/10</span><span>Focus {s.focus}/10</span><span>Workload {s.workload}/10</span><span>Exercise {s.exercise_minutes}m</span></div>)}</div></Section>; }

function History({ outcomes, states, analytics, predictions, minutes }) { return <Section title="Learning History" subtitle="APLO keeps prediction and behavior records so you can see whether its estimates improve." eyebrow="ADAPTATION"><div className="metrics"><Metric label="Outcomes" value={analytics?.outcomes ?? 0} note="observed sessions"/><Metric label="Mean error" value={analytics?.mean_absolute_error_minutes != null ? `${analytics.mean_absolute_error_minutes}m` : "—"} note="absolute duration error"/><Metric label="MAPE" value={analytics?.mean_absolute_percentage_error != null ? `${analytics.mean_absolute_percentage_error}%` : "—"} note="prediction error"/><Metric label="Daily records" value={states.length} note="life-state history"/></div><div className="history-grid"><section className="panel"><div className="panel-head"><div><small>OUTCOME FEEDBACK</small><h3>Predicted vs actual</h3></div></div>{outcomes.slice(0,10).map(o=><div className="history-item" key={o.outcome_id}><div><b>{o.title}</b><span>{new Date(o.created_at).toLocaleString()}</span></div><strong>{o.predicted_duration != null ? minutes(o.predicted_duration) : "—"} → {minutes(o.actual_duration)}</strong><em className={o.duration_error_percent != null && o.duration_error_percent <= 15 ? "good" : "warn"}>{o.duration_error_percent != null ? `${o.duration_error_percent}% error` : "no prediction pair"}</em></div>)}{!outcomes.length&&<Empty text="Record a task outcome to start measuring prediction accuracy."/>}</section><section className="panel"><div className="panel-head"><div><small>PREDICTION LOG</small><h3>Recent model decisions</h3></div><span className="badge">{predictions.length}</span></div>{predictions.slice(0,10).map(p=><div className="prediction-row" key={p.id}><div><b>Task #{p.task_id}</b><span>{new Date(p.prediction_time).toLocaleString()}</span></div><span>{minutes(p.predicted_duration)}</span><span>{Math.round(p.completion_probability*100)}%</span></div>)}</section></div></Section>; }

function Assistant({ question, setQuestion, answer, mode, ask }) { const prompts=["Why was this task scheduled first?","Why is the prediction longer than my estimate?","How does APLO learn from outcomes?","How is my goal progress calculated?"]; return <Section title="APLO Assistant" subtitle="Ask about the system. The assistant explains backend data; it does not invent schedule decisions." eyebrow="EXPLANATION LAYER"><div className="assistant panel"><div className="assistant-head"><div className="assistant-orb">✦</div><div><h3>Explain my optimization</h3><p>Grounded in your current goals, tasks, life state and outcome history.</p></div></div><div className="prompt-row">{prompts.map(p=><button key={p} onClick={()=>ask(p)}>{p}</button>)}</div><div className="assistant-input"><textarea rows="3" placeholder="Ask APLO anything about today's plan…" value={question} onChange={e=>setQuestion(e.target.value)}/><button className="primary" onClick={()=>ask()}>Ask APLO ✦</button></div>{answer&&<div className="answer"><div><span>APLO</span><small>{mode}</small></div><p>{answer}</p></div>}</div></Section>; }

function OutcomeModal({ task, form, setForm, onClose, onSubmit, saving, minutes }) { const delta = Number(form.actual || 0) - Number(task.predicted_duration || 0); return <div className="modal-bg" onMouseDown={e=>e.target===e.currentTarget&&onClose()}><form className="outcome-modal" onSubmit={onSubmit}><button type="button" className="modal-close" onClick={onClose}>×</button><div className="modal-kicker">FEEDBACK LOOP</div><h2>Record real behavior</h2><p className="modal-task">{task.title}</p><div className="prediction-strip"><div><span>APLO predicted</span><b>{minutes(task.predicted_duration)}</b></div><div><span>Your estimate</span><b>{minutes(task.estimated_duration)}</b></div><div><span>Priority</span><b>{task.priority}</b></div></div><div className="form-grid"><Field label="Actual duration (minutes)"><input type="number" min="1" value={form.actual} onChange={e=>setForm({...form,actual:e.target.value})}/></Field><Field label="Rating 1–5"><input type="number" min="1" max="5" step="0.5" value={form.rating} onChange={e=>setForm({...form,rating:e.target.value})}/></Field></div>{form.actual&&<div className={`delta ${delta > 0 ? "over" : "under"}`}>{delta===0?"Exactly on prediction":`${Math.abs(Math.round(delta))}m ${delta>0?"over":"under"} APLO's prediction`}</div>}<label className="complete-toggle"><input type="checkbox" checked={form.completed} onChange={e=>setForm({...form,completed:e.target.checked})}/><span><b>Task completed</b><small>Use this outcome as future behavioral feedback</small></span></label><Field label="Notes"><textarea rows="4" placeholder="What affected the actual duration?" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></Field><button className="primary full" disabled={saving}>{saving?"Recording…":"Record outcome"}</button></form></div>; }

function Section({ title, subtitle, eyebrow="APLO" , children }) { return <section className="content"><div className="section-heading"><div className="section-icon">◆</div><div><small>{eyebrow}</small><h2>{title}</h2><p>{subtitle}</p></div></div>{children}</section>; }
function Field({ label, children, wide }) { return <label className={`field ${wide?"wide":""}`}><span>{label}</span>{children}</label>; }
function Slider({ label,value,min,max,step,suffix,set }) { return <label className="slider"><div><span>{label}</span><b>{value}{suffix}</b></div><input type="range" min={min} max={max} step={step} value={value} onChange={e=>set(e.target.value)}/></label>; }
function Metric({ label,value,note }) { return <div className="metric panel"><small>{label}</small><strong>{value}</strong><span>{note}</span></div>; }
function Bar({ label,value,inverse }) { const width=Math.max(0,Math.min(100,Number(value||0)*10)); return <div className="bar-row"><div><span>{label}</span><b>{Number(value||0).toFixed(1)}/10</b></div><div className="bar"><i className={inverse?"inverse":""} style={{width:`${width}%`}}/></div></div>; }
function Empty({ text }) { return <div className="empty"><b>◇</b><span>{text}</span></div>; }

export default App;
