"use client";

import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bot,
  CheckCircle2,
  ClipboardList,
  Database,
  FileText,
  Gauge,
  Play,
  RefreshCw,
  RotateCcw,
  Send,
  Settings,
  ShieldCheck,
  TerminalSquare
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type {
  Action,
  ActionType,
  ConfigValue,
  Difficulty,
  ModelCatalogResponse,
  ModelCompareResponse,
  ModelRunResult,
  Observation,
  ResetResponse,
  ServiceName,
  StepInfo,
  StepResult,
  TaskCatalogItem,
  TaskCatalogResponse,
  TimelineItem
} from "@/lib/types";

const actionTypes: ActionType[] = [
  "inspect_logs",
  "inspect_metrics",
  "check_status",
  "inspect_config",
  "restart_service",
  "update_config",
  "resolve_incident",
  "escalate"
];
const serviceNames: ServiceName[] = ["web_server", "database", "cache"];
const difficultyFilters: Array<Difficulty | "all"> = ["all", "easy", "medium", "hard"];

export default function Home() {
  const [tasks, setTasks] = useState<TaskCatalogItem[]>([]);
  const [splits, setSplits] = useState<Record<Difficulty, string[]>>({
    easy: [],
    medium: [],
    hard: []
  });
  const [filter, setFilter] = useState<Difficulty | "all">("all");
  const [selectedTaskId, setSelectedTaskId] = useState("cache_crash");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [observation, setObservation] = useState<Observation | null>(null);
  const [lastInfo, setLastInfo] = useState<StepInfo | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [modelA, setModelA] = useState("");
  const [modelB, setModelB] = useState("");
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareResults, setCompareResults] = useState<ModelRunResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionType, setActionType] = useState<ActionType>("inspect_logs");
  const [service, setService] = useState<ServiceName>("web_server");
  const [keyName, setKeyName] = useState("");
  const [value, setValue] = useState("");
  const [rootCause, setRootCause] = useState("");
  const [fix, setFix] = useState("");
  const [reason, setReason] = useState("");
  const [rawAction, setRawAction] = useState("");

  useEffect(() => {
    void loadTasks();
    void loadModels();
  }, []);

  useEffect(() => {
    if (tasks.length > 0 && !tasks.some((task) => task.taskId === selectedTaskId)) {
      setSelectedTaskId(tasks[0].taskId);
    }
  }, [selectedTaskId, tasks]);

  const filteredTasks = useMemo(() => {
    if (filter === "all") {
      return tasks;
    }
    const splitIds = new Set(splits[filter]);
    return tasks.filter((task) => splitIds.has(task.taskId));
  }, [filter, splits, tasks]);

  const selectedTask = tasks.find((task) => task.taskId === selectedTaskId);
  const canRun = Boolean(sessionId && observation && !observation.done && !loading);

  async function loadTasks() {
    setError(null);
    try {
      const data = await requestJson<TaskCatalogResponse>("/api/tasks");
      setTasks(data.tasks);
      setSplits(data.splits);
      setSelectedTaskId(data.tasks[0]?.taskId ?? "cache_crash");
    } catch (requestError) {
      setError(errorText(requestError));
    }
  }

  async function loadModels() {
    try {
      const data = await requestJson<ModelCatalogResponse>("/api/models");
      setModels(data.models);
      setCurrentModel(data.currentModel);
      setHasApiKey(data.hasApiKey);
      const first = data.currentModel ?? data.models[0] ?? "";
      const second = data.models.find((model) => model !== first) ?? "";
      setModelA(first);
      setModelB(second);
    } catch (requestError) {
      setError(errorText(requestError));
    }
  }

  async function resetEpisode(taskId = selectedTaskId) {
    setLoading(true);
    setError(null);
    try {
      const data = await requestJson<ResetResponse>("/api/episode/reset", {
        method: "POST",
        body: JSON.stringify({ taskId })
      });
      setSessionId(data.sessionId);
      setObservation(data.observation);
      setLastInfo(null);
      setTimeline([]);
      setCompareResults([]);
      setSelectedTaskId(taskId);
      setRawAction("");
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function submitAction(action: Action, raw?: string) {
    if (!sessionId) {
      setError("Reset an episode before running actions.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await requestJson<StepResult>("/api/episode/step", {
        method: "POST",
        body: JSON.stringify({
          sessionId,
          action: raw ? undefined : action,
          rawAction: raw
        })
      });
      setObservation(result.observation);
      setLastInfo(result.info);
      setTimeline((items) => [
        ...items,
        {
          step: result.observation.step,
          action: result.observation.lastAction ?? "",
          reward: result.reward,
          summary: result.observation.lastResult.summary,
          error: result.observation.lastResult.error
        }
      ]);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setLoading(false);
    }
  }

  async function runModelCompare() {
    if (!selectedTaskId || !modelA || !modelB) {
      setError("Choose a task and two models before running a comparison.");
      return;
    }
    setCompareLoading(true);
    setError(null);
    setCompareResults([]);
    try {
      const data = await requestJson<ModelCompareResponse>("/api/baseline/compare", {
        method: "POST",
        body: JSON.stringify({
          taskId: selectedTaskId,
          modelA,
          modelB
        })
      });
      setCompareResults(data.results);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setCompareLoading(false);
    }
  }

  function buildAction(): Action {
    if (actionType === "resolve_incident") {
      return { actionType, rootCause, fix };
    }
    if (actionType === "escalate") {
      return { actionType, reason };
    }
    if (actionType === "update_config") {
      return { actionType, service, key: keyName, value: parseConfigValue(value) };
    }
    if (actionType === "inspect_config") {
      return { actionType, service, key: keyName || undefined };
    }
    return { actionType, service };
  }

  function loadActionTemplate(nextActionType: ActionType) {
    setActionType(nextActionType);
    if (nextActionType === "update_config" && !keyName) {
      setKeyName(defaultKeyForService(service));
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">SRE-Zero Phase 1</div>
          <h1>SRE-Zero Console</h1>
        </div>
        <div className="topbarActions">
          <button className="secondaryButton" type="button" onClick={() => void loadTasks()}>
            <RefreshCw size={16} />
            Refresh
          </button>
          <button
            className="primaryButton"
            type="button"
            onClick={() => void resetEpisode(selectedTaskId)}
            disabled={!selectedTaskId || loading}
          >
            <Play size={16} />
            Start Episode
          </button>
        </div>
      </header>

      {error ? (
        <section className="errorBand">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </section>
      ) : null}

      <section className="workspace">
        <aside className="sidebar panel">
          <div className="panelHeader">
            <ClipboardList size={18} />
            <h2>Task Suite</h2>
          </div>
          <div className="segmented" aria-label="Difficulty filter">
            {difficultyFilters.map((item) => (
              <button
                key={item}
                className={filter === item ? "segment active" : "segment"}
                type="button"
                onClick={() => setFilter(item)}
              >
                {item}
              </button>
            ))}
          </div>
          <div className="taskList">
            {filteredTasks.map((task) => (
              <button
                key={task.taskId}
                className={task.taskId === selectedTaskId ? "taskItem selected" : "taskItem"}
                type="button"
                onClick={() => {
                  setSelectedTaskId(task.taskId);
                  void resetEpisode(task.taskId);
                }}
              >
                <span className={`difficulty ${task.difficulty}`}>{task.difficulty}</span>
                <span className="taskId">{task.taskId}</span>
                <span className="taskAlert">{task.alert}</span>
              </button>
            ))}
          </div>
        </aside>

        <section className="mainColumn">
          <section className="panel alertPanel">
            <div className="panelHeader">
              <ShieldCheck size={18} />
              <h2>Incident</h2>
              {observation?.done ? (
                <span className={lastInfo?.metricsSoFar.success ? "statusPill success" : "statusPill done"}>
                  {lastInfo?.metricsSoFar.success ? "resolved" : "done"}
                </span>
              ) : (
                <span className="statusPill active">active</span>
              )}
            </div>
            <p className="alertText">{observation?.alert ?? selectedTask?.alert ?? "Start an episode."}</p>
            <div className="episodeMeta">
              <span>Task: {observation?.incidentId ?? selectedTaskId}</span>
              <span>Step: {observation?.step ?? 0}</span>
              <span>Remaining: {observation?.stepsRemaining ?? "-"}</span>
              <span>Session: {sessionId ? shortId(sessionId) : "not started"}</span>
            </div>
          </section>

          <section className="panel actionPanel">
            <div className="panelHeader">
              <TerminalSquare size={18} />
              <h2>Action Builder</h2>
            </div>
            <div className="toolGrid">
              <ToolButton icon={<FileText size={16} />} label="Logs" onClick={() => loadActionTemplate("inspect_logs")} />
              <ToolButton icon={<BarChart3 size={16} />} label="Metrics" onClick={() => loadActionTemplate("inspect_metrics")} />
              <ToolButton icon={<Gauge size={16} />} label="Status" onClick={() => loadActionTemplate("check_status")} />
              <ToolButton icon={<Settings size={16} />} label="Config" onClick={() => loadActionTemplate("inspect_config")} />
              <ToolButton icon={<RotateCcw size={16} />} label="Restart" onClick={() => loadActionTemplate("restart_service")} />
              <ToolButton icon={<Database size={16} />} label="Update" onClick={() => loadActionTemplate("update_config")} />
              <ToolButton icon={<CheckCircle2 size={16} />} label="Resolve" onClick={() => loadActionTemplate("resolve_incident")} />
              <ToolButton icon={<AlertTriangle size={16} />} label="Escalate" onClick={() => loadActionTemplate("escalate")} />
            </div>

            <div className="formGrid">
              <label>
                Action
                <select value={actionType} onChange={(event) => setActionType(event.target.value as ActionType)}>
                  {actionTypes.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              {needsService(actionType) ? (
                <label>
                  Service
                  <select value={service} onChange={(event) => setService(event.target.value as ServiceName)}>
                    {serviceNames.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              {needsKey(actionType) ? (
                <label>
                  Key
                  <input
                    value={keyName}
                    onChange={(event) => setKeyName(event.target.value)}
                    placeholder={defaultKeyForService(service)}
                  />
                </label>
              ) : null}
              {actionType === "update_config" ? (
                <label>
                  Value
                  <input
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                    placeholder="100, true, cache.internal"
                  />
                </label>
              ) : null}
              {actionType === "resolve_incident" ? (
                <>
                  <label className="wide">
                    Root cause
                    <input
                      value={rootCause}
                      onChange={(event) => setRootCause(event.target.value)}
                      placeholder="database connection pool exhaustion"
                    />
                  </label>
                  <label className="wide">
                    Fix
                    <input
                      value={fix}
                      onChange={(event) => setFix(event.target.value)}
                      placeholder="increase database pool size"
                    />
                  </label>
                </>
              ) : null}
              {actionType === "escalate" ? (
                <label className="wide">
                  Reason
                  <input
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                    placeholder="Need human review"
                  />
                </label>
              ) : null}
            </div>

            <div className="actionFooter">
              <code>{formatPreview(buildAction())}</code>
              <button
                className="primaryButton"
                type="button"
                disabled={!canRun}
                onClick={() => void submitAction(buildAction())}
              >
                <Send size={16} />
                Run Action
              </button>
            </div>

            <div className="rawRow">
              <input
                value={rawAction}
                onChange={(event) => setRawAction(event.target.value)}
                placeholder="Raw action, e.g. inspect_logs(web_server)"
              />
              <button
                className="secondaryButton"
                type="button"
                disabled={!canRun || !rawAction.trim()}
                onClick={() => void submitAction(buildAction(), rawAction)}
              >
                Run Raw
              </button>
            </div>
          </section>

          <section className="panel resultPanel">
            <div className="panelHeader">
              <Activity size={18} />
              <h2>Last Observation</h2>
            </div>
            <div className="resultSummary">
              {observation?.lastResult.summary ?? "No action has been run yet."}
            </div>
            <pre className="detailsBlock">
              {JSON.stringify(observation?.lastResult.details ?? {}, null, 2)}
            </pre>
          </section>
        </section>

        <aside className="rightRail">
          <section className="panel">
            <div className="panelHeader">
              <Bot size={18} />
              <h2>Model Baselines</h2>
            </div>
            <div className="modelPanel">
              <div className="modelStatus">
                <span>{models.length} models</span>
                <span>{hasApiKey ? "API key loaded" : "API key missing"}</span>
                <span>Default: {currentModel ?? "unset"}</span>
              </div>
              <label>
                Model A
                <select value={modelA} onChange={(event) => setModelA(event.target.value)}>
                  {models.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Model B
                <select value={modelB} onChange={(event) => setModelB(event.target.value)}>
                  {models.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="primaryButton fullWidth"
                type="button"
                disabled={compareLoading || !modelA || !modelB || modelA === modelB}
                onClick={() => void runModelCompare()}
              >
                <Play size={16} />
                {compareLoading ? "Running..." : "Compare on Task"}
              </button>
              {compareResults.length ? (
                <div className="compareList">
                  {compareResults.map((result) => (
                    <ModelResult key={result.model} result={result} />
                  ))}
                </div>
              ) : (
                <p className="emptyText compact">
                  Runs one prompting baseline episode per selected model on the current task.
                </p>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="panelHeader">
              <Gauge size={18} />
              <h2>Metrics</h2>
            </div>
            <MetricList info={lastInfo} />
          </section>

          <section className="panel">
            <div className="panelHeader">
              <Bot size={18} />
              <h2>Known Findings</h2>
            </div>
            {observation?.knownFindings.length ? (
              <ul className="findingList">
                {observation.knownFindings.map((finding) => (
                  <li key={finding}>{finding}</li>
                ))}
              </ul>
            ) : (
              <p className="emptyText">No evidence gathered yet.</p>
            )}
          </section>

          <section className="panel">
            <div className="panelHeader">
              <ClipboardList size={18} />
              <h2>Trajectory</h2>
            </div>
            <div className="timeline">
              {timeline.length ? (
                timeline.map((item) => (
                  <div className="timelineItem" key={`${item.step}-${item.action}`}>
                    <div>
                      <span className="stepBadge">{item.step}</span>
                      <code>{item.action}</code>
                    </div>
                    <p>{item.summary}</p>
                    <span className={item.reward >= 0 ? "reward positive" : "reward negative"}>
                      {item.reward.toFixed(3)}
                    </span>
                  </div>
                ))
              ) : (
                <p className="emptyText">Run an action to start the trajectory.</p>
              )}
            </div>
          </section>
        </aside>
      </section>
    </main>
  );
}

function ModelResult({ result }: { result: ModelRunResult }) {
  return (
    <div className={result.error ? "modelResult failed" : "modelResult"}>
      <div className="modelResultHeader">
        <strong>{result.model}</strong>
        <span className={result.success ? "statusPill success" : "statusPill done"}>
          {result.success ? "resolved" : "not resolved"}
        </span>
      </div>
      <Metric label="Reward" value={result.finalReward.toFixed(3)} />
      <Metric label="Steps" value={String(result.totalSteps)} />
      <Metric label="Invalid" value={String(result.invalidActions)} />
      <Metric label="Evidence" value={`${Math.round(result.evidenceCoverage * 100)}%`} />
      {result.terminalReason ? <p>{result.terminalReason}</p> : null}
      {result.error ? <p className="modelError">{result.error}</p> : null}
    </div>
  );
}

function ToolButton({
  icon,
  label,
  onClick
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button className="toolButton" type="button" onClick={onClick} title={label}>
      {icon}
      <span>{label}</span>
    </button>
  );
}

function MetricList({ info }: { info: StepInfo | null }) {
  if (!info) {
    return <p className="emptyText">Metrics appear after the first action.</p>;
  }
  const metrics = info.metricsSoFar;
  const componentRows = Object.entries(info.rewardComponents.components);
  const penaltyRows = Object.entries(info.rewardComponents.penalties).filter(([, value]) => value !== 0);
  return (
    <div className="metricStack">
      <Metric label="Success" value={metrics.success ? "yes" : "no"} />
      <Metric label="Total steps" value={String(metrics.totalSteps)} />
      <Metric label="Invalid actions" value={String(metrics.invalidActions)} />
      <Metric label="Wrong remediations" value={String(metrics.wrongRemediations)} />
      <Metric label="Evidence" value={`${Math.round(info.evidenceCoverage * 100)}%`} />
      <Metric label="Final reward" value={metrics.finalReward.toFixed(3)} />
      <div className="rewardRows">
        {componentRows.map(([name, value]) => (
          <div className="rewardRow" key={name}>
            <span>{name}</span>
            <span>{value.toFixed(3)}</span>
          </div>
        ))}
        {penaltyRows.map(([name, value]) => (
          <div className="rewardRow penalty" key={name}>
            <span>{name}</span>
            <span>{value.toFixed(3)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  const data = (await response.json()) as T & { error?: string };
  if (!response.ok) {
    throw new Error(data.error ?? `Request failed with ${response.status}`);
  }
  return data;
}

function needsService(actionType: ActionType): boolean {
  return !["resolve_incident", "escalate"].includes(actionType);
}

function needsKey(actionType: ActionType): boolean {
  return actionType === "inspect_config" || actionType === "update_config";
}

function defaultKeyForService(service: ServiceName): string {
  if (service === "web_server") {
    return "TIMEOUT_MS";
  }
  if (service === "database") {
    return "DB_POOL_SIZE";
  }
  return "TTL_SECONDS";
}

function parseConfigValue(input: string): ConfigValue {
  const trimmed = input.trim();
  if (trimmed.toLowerCase() === "true") {
    return true;
  }
  if (trimmed.toLowerCase() === "false") {
    return false;
  }
  const numeric = Number(trimmed);
  return Number.isNaN(numeric) || trimmed.length === 0 ? trimmed : numeric;
}

function formatPreview(action: Action): string {
  if (action.actionType === "resolve_incident") {
    return `resolve_incident(${action.rootCause || "root_cause"}, ${action.fix || "fix"})`;
  }
  if (action.actionType === "escalate") {
    return `escalate(${action.reason || "reason"})`;
  }
  if (action.actionType === "inspect_config") {
    return action.key
      ? `inspect_config(${action.service}, ${action.key})`
      : `inspect_config(${action.service})`;
  }
  if (action.actionType === "update_config") {
    return `update_config(${action.service}, ${action.key || "KEY"}, ${String(action.value)})`;
  }
  return `${action.actionType}(${action.service})`;
}

function shortId(value: string): string {
  return value.slice(0, 8);
}

function errorText(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
