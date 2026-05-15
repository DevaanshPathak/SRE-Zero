import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import type {
  Action,
  ActionResult,
  ActionType,
  ConfigValue,
  Difficulty,
  EpisodeMetrics,
  Observation,
  RewardBreakdown,
  ServiceName,
  StepInfo,
  StepResult,
  TaskCatalogItem
} from "./types";

export type JsonAction = Action | string | Record<string, unknown>;

interface CorrectFixConfig {
  action_type: ActionType;
  service: ServiceName;
  key?: string;
  min_numeric_value?: number;
  exact_value?: ConfigValue;
  fix_keywords?: string[];
}

interface ServicePatchConfig {
  status?: string;
  logs?: string[];
  metrics?: Record<string, number | string>;
  config?: Record<string, ConfigValue>;
  dependencies?: ServiceName[];
}

interface TaskConfig {
  task_id: string;
  difficulty: Difficulty;
  alert: string;
  root_cause: string;
  root_cause_keywords: string[];
  relevant_evidence: string[];
  evidence_descriptions: Record<string, string>;
  correct_fix: CorrectFixConfig;
  service_patches: Partial<Record<ServiceName, ServicePatchConfig>>;
  expected_action_pattern: string[];
  distractors: string[];
  distractor_services?: ServiceName[];
  max_steps: number;
  terminal_on_wrong_resolution?: boolean;
  metadata?: Record<string, string>;
}

interface ServiceState {
  name: ServiceName;
  status: string;
  logs: string[];
  metrics: Record<string, number | string>;
  config: Record<string, ConfigValue>;
  dependencies: ServiceName[];
}

interface RewardState {
  components: Record<string, number>;
  penalties: Record<string, number>;
}

const SERVICES: ServiceName[] = [
  "web_server",
  "database",
  "cache",
  "message_queue",
  "load_balancer"
];
const SERVICE_ACTIONS = new Set<ActionType>([
  "inspect_logs",
  "inspect_metrics",
  "check_status",
  "inspect_config",
  "restart_service",
  "update_config"
]);
const COMPONENT_MAX: Record<string, number> = {
  evidence: 0.2,
  root_cause: 0.25,
  remediation: 0.25,
  resolution: 0.2,
  efficiency: 0.1
};
const PENALTY_VALUES: Record<string, number> = {
  invalid_action: -0.05,
  repeated_invalid_action: -0.1,
  wrong_remediation: -0.15,
  premature_resolution: -0.2,
  restart_unrelated_service: -0.1,
  repeated_useless_action: -0.05
};
const AVAILABLE_TOOLS = [
  "inspect_logs(service)",
  "inspect_metrics(service)",
  "check_status(service)",
  "inspect_config(service, key?)",
  "restart_service(service)",
  "update_config(service, key, value)",
  "resolve_incident(root_cause, fix)",
  "escalate(reason)"
];
const ACTION_NAMES: ActionType[] = [
  "inspect_logs",
  "inspect_metrics",
  "check_status",
  "inspect_config",
  "restart_service",
  "update_config",
  "resolve_incident",
  "escalate"
];

const repoRoot = path.resolve(process.cwd(), "..");
const configDir = path.join(repoRoot, "srezero", "task_configs");
const splitsPath = path.join(repoRoot, "srezero", "task_splits.json");

export class SimulatorEpisode {
  readonly sessionId: string;
  readonly task: TaskConfig;
  services: Record<ServiceName, ServiceState>;
  stepCount = 0;
  done = false;
  knownFindings: string[] = [];
  evidenceFound = new Set<string>();
  metrics: EpisodeMetrics = initialMetrics();
  rewardState: RewardState = {
    components: Object.fromEntries(Object.keys(COMPONENT_MAX).map((key) => [key, 0])),
    penalties: Object.fromEntries(Object.keys(PENALTY_VALUES).map((key) => [key, 0]))
  };
  seenActions = new Map<string, number>();
  seenInvalidActions = new Map<string, number>();
  correctRemediationApplied = false;
  lastTerminalReason: string | null = null;

  constructor(task: TaskConfig) {
    this.sessionId = crypto.randomUUID();
    this.task = task;
    this.services = buildServices(task);
  }

  initialObservation(): Observation {
    return this.observation(null, {
      summary: "Incident opened.",
      details: { difficulty: this.task.difficulty },
      error: null
    });
  }

  step(input: JsonAction): StepResult {
    if (this.done) {
      return {
        observation: this.observation(null, {
          summary: "Episode is already done.",
          details: { terminalReason: this.lastTerminalReason },
          error: "episode_done"
        }),
        reward: 0,
        done: true,
        info: this.info(false, this.lastTerminalReason)
      };
    }

    const previousRaw = this.rawScore();
    let invalidAction = false;
    let terminalReason: string | null = null;
    let canonicalAction: string | null = null;
    let result: ActionResult;

    try {
      const action = parseAction(input);
      canonicalAction = formatAction(action);
      this.stepCount += 1;
      this.metrics.totalSteps += 1;

      if (this.hasInvalidService(action)) {
        invalidAction = true;
        result = this.recordInvalidAction(canonicalAction, "invalid_service", false, {
          service: action.service
        });
      } else {
        const repeated = (this.seenActions.get(canonicalAction) ?? 0) > 0;
        this.seenActions.set(canonicalAction, (this.seenActions.get(canonicalAction) ?? 0) + 1);
        const executed = this.executeAction(action);
        result = executed.result;
        terminalReason = executed.terminalReason;
        const newEvidence = this.recordEvidence(action);

        if (repeated && !newEvidence && action.actionType !== "resolve_incident") {
          this.metrics.repeatedActions += 1;
          this.addPenalty("repeated_useless_action");
        }
      }
    } catch (error) {
      invalidAction = true;
      canonicalAction = String(input);
      result = this.recordInvalidAction(canonicalAction, errorMessage(error), true);
    }

    if (!this.done && this.stepCount >= this.task.max_steps) {
      this.done = true;
      terminalReason = terminalReason ?? "step_budget_exhausted";
    }

    if (this.done) {
      this.lastTerminalReason = terminalReason;
      this.metrics.finalReward = this.episodeScore();
    }

    const reward = clamp(this.rawScore() - previousRaw, -1, 1);
    return {
      observation: this.observation(canonicalAction, result),
      reward,
      done: this.done,
      info: this.info(invalidAction, terminalReason)
    };
  }

  private executeAction(action: Action): { result: ActionResult; terminalReason: string | null } {
    switch (action.actionType) {
      case "inspect_logs": {
        const service = this.service(action.service);
        return {
          result: {
            summary: `Inspected logs for ${service.name}.`,
            details: { service: service.name, logs: service.logs },
            error: null
          },
          terminalReason: null
        };
      }
      case "inspect_metrics": {
        const service = this.service(action.service);
        return {
          result: {
            summary: `Inspected metrics for ${service.name}.`,
            details: { service: service.name, metrics: service.metrics },
            error: null
          },
          terminalReason: null
        };
      }
      case "check_status": {
        const service = this.service(action.service);
        return {
          result: {
            summary: `${service.name} status is ${service.status}.`,
            details: { service: service.name, status: service.status },
            error: null
          },
          terminalReason: null
        };
      }
      case "inspect_config": {
        const service = this.service(action.service);
        const config = action.key ? { [action.key]: service.config[action.key] } : service.config;
        return {
          result: {
            summary: `Inspected config for ${service.name}.`,
            details: { service: service.name, config },
            error: null
          },
          terminalReason: null
        };
      }
      case "restart_service":
        return { result: this.restartService(action), terminalReason: null };
      case "update_config":
        return { result: this.updateConfig(action), terminalReason: null };
      case "resolve_incident":
        return this.resolveIncident(action);
      case "escalate":
        this.done = true;
        return {
          result: {
            summary: "Incident escalated.",
            details: { reason: action.reason },
            error: null
          },
          terminalReason: "escalated"
        };
    }
  }

  private restartService(action: Action): ActionResult {
    const service = this.service(action.service);
    this.metrics.remediationActions += 1;
    service.status = "healthy";
    service.logs.push("INFO service restarted by incident responder");

    if (this.remediationMatches(action)) {
      this.correctRemediationApplied = true;
      this.markComponent("remediation");
      return {
        summary: `Restarted ${service.name}.`,
        details: { service: service.name, status: service.status, correctRemediation: true },
        error: null
      };
    }

    this.metrics.wrongRemediations += 1;
    this.recordDistractorFailure(action);
    this.addPenalty("wrong_remediation");
    if (action.service !== this.task.correct_fix.service) {
      this.addPenalty("restart_unrelated_service");
    }
    return {
      summary: `Restarted ${service.name}, but the incident persists.`,
      details: { service: service.name, correctRemediation: false },
      error: null
    };
  }

  private updateConfig(action: Action): ActionResult {
    const service = this.service(action.service);
    this.metrics.remediationActions += 1;
    const key = requireField(action.key, "update_config requires key.");
    const value = action.value;
    const previous = service.config[key];
    if (value !== undefined) {
      service.config[key] = value;
    }

    if (this.remediationMatches(action)) {
      this.correctRemediationApplied = true;
      this.markComponent("remediation");
      return {
        summary: `Updated ${service.name} config ${key}.`,
        details: { service: service.name, key, previous, value, correctRemediation: true },
        error: null
      };
    }

    this.metrics.wrongRemediations += 1;
    this.recordDistractorFailure(action);
    this.addPenalty("wrong_remediation");
    return {
      summary: `Updated ${service.name} config, but the incident persists.`,
      details: { service: service.name, key, previous, value, correctRemediation: false },
      error: null
    };
  }

  private resolveIncident(action: Action): { result: ActionResult; terminalReason: string | null } {
    const rootOk = this.matchesRootCause(action.rootCause ?? "");
    const fixOk = this.matchesFixText(action.fix ?? "");

    if (rootOk) {
      this.markComponent("root_cause");
    }

    if (rootOk && fixOk && this.correctRemediationApplied) {
      this.markComponent("resolution");
      this.rewardState.components.efficiency =
        COMPONENT_MAX.efficiency * Math.max(0, (this.task.max_steps - this.stepCount) / this.task.max_steps);
      this.done = true;
      this.metrics.success = true;
      return {
        result: {
          summary: "Incident resolved.",
          details: { rootCauseMatch: true, fixMatch: true },
          error: null
        },
        terminalReason: "resolved"
      };
    }

    this.metrics.prematureResolutions += 1;
    this.addPenalty("premature_resolution");
    const terminalOnWrong = this.task.terminal_on_wrong_resolution ?? true;
    if (terminalOnWrong) {
      this.done = true;
    }
    return {
      result: {
        summary: "Resolution rejected.",
        details: {
          rootCauseMatch: rootOk,
          fixMatch: fixOk,
          remediationApplied: this.correctRemediationApplied
        },
        error: "resolution_rejected"
      },
      terminalReason: terminalOnWrong ? "premature_or_incorrect_resolution" : null
    };
  }

  private recordEvidence(action: Action): boolean {
    const keys = this.matchingEvidenceKeys(action).filter((key) => !this.evidenceFound.has(key));
    if (keys.length === 0) {
      return false;
    }

    for (const key of keys) {
      this.evidenceFound.add(key);
      const finding = this.task.evidence_descriptions[key] ?? key;
      if (!this.knownFindings.includes(finding)) {
        this.knownFindings.push(finding);
      }
    }
    this.metrics.evidenceActions += 1;
    this.rewardState.components.evidence =
      COMPONENT_MAX.evidence * (this.evidenceFound.size / Math.max(1, this.task.relevant_evidence.length));
    return true;
  }

  private recordDistractorFailure(action: Action): void {
    if (
      action.service &&
      isServiceName(action.service) &&
      this.task.distractor_services?.includes(action.service)
    ) {
      this.metrics.distractorFailures += 1;
    }
  }

  private matchingEvidenceKeys(action: Action): string[] {
    if (!action.service) {
      return [];
    }
    const baseKey = `${action.actionType}:${action.service}`;
    const candidates = [baseKey];
    if (action.actionType === "inspect_config") {
      if (action.key) {
        candidates.push(`${baseKey}:${action.key.toUpperCase()}`);
      } else {
        candidates.push(
          ...this.task.relevant_evidence.filter((key) => key.startsWith(`${baseKey}:`))
        );
      }
    }
    return candidates.filter((key) => this.task.relevant_evidence.includes(key));
  }

  private remediationMatches(action: Action): boolean {
    const fix = this.task.correct_fix;
    if (fix.action_type !== action.actionType || fix.service !== action.service) {
      return false;
    }
    if (fix.action_type === "restart_service") {
      return true;
    }
    if (fix.action_type !== "update_config") {
      return false;
    }
    if (fix.key && (action.key ?? "").toUpperCase() !== fix.key.toUpperCase()) {
      return false;
    }
    if ("exact_value" in fix) {
      return action.value === fix.exact_value;
    }
    if (typeof fix.min_numeric_value === "number") {
      return Number(action.value) >= fix.min_numeric_value;
    }
    return true;
  }

  private matchesRootCause(text: string): boolean {
    const normalized = normalizeText(text);
    if (normalized.includes(normalizeText(this.task.root_cause))) {
      return true;
    }
    const matches = this.task.root_cause_keywords.filter((keyword) =>
      normalized.includes(normalizeText(keyword))
    ).length;
    return matches >= Math.max(1, Math.ceil(this.task.root_cause_keywords.length / 2));
  }

  private matchesFixText(text: string): boolean {
    const keywords = this.task.correct_fix.fix_keywords ?? [];
    const normalized = normalizeText(text);
    return keywords.every((keyword) => normalized.includes(normalizeText(keyword)));
  }

  private service(serviceName?: string): ServiceState {
    if (!serviceName || !isServiceName(serviceName)) {
      throw new Error(`Invalid service: ${serviceName ?? "missing"}`);
    }
    return this.services[serviceName];
  }

  private hasInvalidService(action: Action): boolean {
    return SERVICE_ACTIONS.has(action.actionType) && (!action.service || !isServiceName(action.service));
  }

  private recordInvalidAction(
    canonicalAction: string,
    error: string,
    incrementStep: boolean,
    details: Record<string, unknown> = {}
  ): ActionResult {
    if (incrementStep) {
      this.stepCount += 1;
      this.metrics.totalSteps += 1;
    }
    this.metrics.invalidActions += 1;
    this.seenInvalidActions.set(
      canonicalAction,
      (this.seenInvalidActions.get(canonicalAction) ?? 0) + 1
    );
    if ((this.seenInvalidActions.get(canonicalAction) ?? 0) > 1) {
      this.metrics.repeatedActions += 1;
      this.addPenalty("repeated_invalid_action");
    } else {
      this.addPenalty("invalid_action");
    }
    return {
      summary: "Invalid action.",
      details: { action: canonicalAction, ...details },
      error
    };
  }

  private addPenalty(name: string): void {
    this.rewardState.penalties[name] = (this.rewardState.penalties[name] ?? 0) + PENALTY_VALUES[name];
  }

  private markComponent(name: string): void {
    this.rewardState.components[name] = COMPONENT_MAX[name];
  }

  private rawScore(): number {
    return (
      Object.values(this.rewardState.components).reduce((total, value) => total + value, 0) +
      Object.values(this.rewardState.penalties).reduce((total, value) => total + value, 0)
    );
  }

  private episodeScore(): number {
    return clamp(this.rawScore(), 0, 1);
  }

  private rewardBreakdown(): RewardBreakdown {
    return {
      components: { ...this.rewardState.components },
      penalties: { ...this.rewardState.penalties },
      rawTotal: this.rawScore(),
      total: this.episodeScore()
    };
  }

  private observation(lastAction: string | null, lastResult: ActionResult): Observation {
    return {
      incidentId: this.task.task_id,
      step: this.stepCount,
      stepsRemaining: Math.max(0, this.task.max_steps - this.stepCount),
      alert: this.task.alert,
      lastAction,
      lastResult,
      knownFindings: [...this.knownFindings],
      availableTools: AVAILABLE_TOOLS,
      done: this.done
    };
  }

  private info(invalidAction: boolean, terminalReason: string | null): StepInfo {
    return {
      rewardComponents: this.rewardBreakdown(),
      invalidAction,
      terminalReason,
      metricsSoFar: { ...this.metrics },
      evidenceCoverage: this.evidenceFound.size / Math.max(1, this.task.relevant_evidence.length)
    };
  }
}

export function listTasks(): TaskCatalogItem[] {
  const splits = loadSplits();
  const orderedIds = [...splits.easy, ...splits.medium, ...splits.hard];
  return orderedIds.map((taskId) => {
    const task = loadTask(taskId);
    return {
      taskId: task.task_id,
      difficulty: task.difficulty,
      alert: task.alert
    };
  });
}

export function loadSplits(): Record<Difficulty, string[]> {
  return JSON.parse(fs.readFileSync(splitsPath, "utf-8")) as Record<Difficulty, string[]>;
}

export function createEpisode(taskId: string): SimulatorEpisode {
  return new SimulatorEpisode(loadTask(taskId));
}

export function getSession(sessionId: string): SimulatorEpisode | undefined {
  return sessionStore().get(sessionId);
}

export function saveSession(session: SimulatorEpisode): void {
  sessionStore().set(session.sessionId, session);
}

function loadTask(taskId: string): TaskConfig {
  const taskPath = path.join(configDir, `${taskId}.json`);
  return JSON.parse(fs.readFileSync(taskPath, "utf-8")) as TaskConfig;
}

function sessionStore(): Map<string, SimulatorEpisode> {
  const globalStore = globalThis as typeof globalThis & {
    __sreZeroSessions?: Map<string, SimulatorEpisode>;
  };
  globalStore.__sreZeroSessions ??= new Map<string, SimulatorEpisode>();
  return globalStore.__sreZeroSessions;
}

function buildServices(task: TaskConfig): Record<ServiceName, ServiceState> {
  const services = baseServices();
  for (const serviceName of SERVICES) {
    const patch = task.service_patches[serviceName];
    if (!patch) {
      continue;
    }
    const service = services[serviceName];
    if (patch.status) {
      service.status = patch.status;
    }
    if (patch.logs) {
      service.logs = [...patch.logs];
    }
    if (patch.metrics) {
      service.metrics = { ...service.metrics, ...patch.metrics };
    }
    if (patch.config) {
      service.config = { ...service.config, ...patch.config };
    }
    if (patch.dependencies) {
      service.dependencies = [...patch.dependencies];
    }
  }
  return services;
}

function baseServices(): Record<ServiceName, ServiceState> {
  return {
    web_server: {
      name: "web_server",
      status: "healthy",
      logs: [
        "INFO request_id=1001 path=/ status=200 latency_ms=42",
        "INFO request_id=1002 path=/checkout status=200 latency_ms=88"
      ],
      metrics: {
        request_rate: 240,
        error_rate: 0.01,
        p95_latency_ms: 120,
        upstream_timeout_rate: 0
      },
      config: { TIMEOUT_MS: 3000, MAX_WORKERS: 16 },
      dependencies: ["database", "cache", "message_queue"]
    },
    database: {
      name: "database",
      status: "healthy",
      logs: [
        "INFO connection pool initialized size=50",
        "INFO query completed table=orders latency_ms=18"
      ],
      metrics: {
        active_connections: 14,
        max_connections: 50,
        connection_wait_ms: 3,
        query_p95_latency_ms: 35
      },
      config: { DB_POOL_SIZE: 50, QUERY_TIMEOUT_MS: 2000 },
      dependencies: []
    },
    cache: {
      name: "cache",
      status: "healthy",
      logs: [
        "INFO cache warmed namespace=products keys=4200",
        "INFO eviction cycle completed evicted=12"
      ],
      metrics: { hit_rate: 0.92, p95_latency_ms: 5, memory_used_pct: 45 },
      config: { TTL_SECONDS: 300, MAX_MEMORY_MB: 512 },
      dependencies: []
    },
    message_queue: {
      name: "message_queue",
      status: "healthy",
      logs: [
        "INFO queue=checkout_jobs consumers=8 backlog=24",
        "INFO publish latency_ms=12 ack_rate=0.99"
      ],
      metrics: {
        queue_depth: 24,
        oldest_message_age_ms: 1200,
        publish_error_rate: 0,
        consumer_lag_ms: 250,
        dead_letter_rate: 0
      },
      config: {
        CONSUMER_CONCURRENCY: 8,
        MAX_IN_FLIGHT: 500,
        RETRY_LIMIT: 3,
        VISIBILITY_TIMEOUT_MS: 30000
      },
      dependencies: ["database"]
    },
    load_balancer: {
      name: "load_balancer",
      status: "healthy",
      logs: [
        "INFO backend=web_server healthy=true weight=50",
        "INFO listener=https status=active tls_days_remaining=45"
      ],
      metrics: {
        request_rate: 260,
        backend_5xx_rate: 0.01,
        healthy_backends: 2,
        connection_utilization_pct: 42,
        p95_latency_ms: 55
      },
      config: {
        HEALTH_CHECK_PATH: "/healthz",
        MAX_CONNECTIONS: 2000,
        STICKY_SESSIONS: false,
        WEB_WEIGHT_PRIMARY: 50
      },
      dependencies: ["web_server"]
    }
  };
}

function parseAction(input: JsonAction): Action {
  if (typeof input === "string") {
    return parseActionString(input);
  }
  const record = input as Record<string, unknown>;
  const actionType = stringField(record.actionType ?? record.action_type, "Missing action type.");
  if (!ACTION_NAMES.includes(actionType as ActionType)) {
    throw new Error(`Unknown action: ${actionType}`);
  }
  const action: Action = {
    actionType: actionType as ActionType,
    service: optionalString(record.service),
    key: optionalString(record.key),
    value: record.value as ConfigValue | undefined,
    rootCause: optionalString(record.rootCause ?? record.root_cause),
    fix: optionalString(record.fix),
    reason: optionalString(record.reason)
  };
  validateAction(action);
  return action;
}

function parseActionString(input: string): Action {
  const match = input.trim().match(/^([a-zA-Z_][a-zA-Z0-9_]*)\((.*)\)$/);
  if (!match) {
    throw new Error("Action must use function-call syntax.");
  }
  const actionType = match[1] as ActionType;
  if (!ACTION_NAMES.includes(actionType)) {
    throw new Error(`Unknown action: ${actionType}`);
  }
  const args = splitArgs(match[2]);
  switch (actionType) {
    case "inspect_logs":
    case "inspect_metrics":
    case "check_status":
    case "restart_service":
      if (args.length !== 1) {
        throw new Error(`${actionType} requires exactly one service argument.`);
      }
      return { actionType, service: args[0] };
    case "inspect_config":
      if (args.length !== 1 && args.length !== 2) {
        throw new Error("inspect_config requires service and optional key arguments.");
      }
      return { actionType, service: args[0], key: args[1] };
    case "update_config":
      if (args.length !== 3) {
        throw new Error("update_config requires service, key, and value arguments.");
      }
      return { actionType, service: args[0], key: args[1], value: coerceValue(args[2]) };
    case "resolve_incident":
      if (args.length !== 2) {
        throw new Error("resolve_incident requires root_cause and fix arguments.");
      }
      return { actionType, rootCause: args[0], fix: args[1] };
    case "escalate":
      if (args.length !== 1) {
        throw new Error("escalate requires one reason argument.");
      }
      return { actionType, reason: args[0] };
  }
}

function validateAction(action: Action): void {
  if (SERVICE_ACTIONS.has(action.actionType) && !action.service) {
    throw new Error(`${action.actionType} requires a service.`);
  }
  if (action.actionType === "update_config" && (!action.key || action.value === undefined)) {
    throw new Error("update_config requires key and value.");
  }
  if (action.actionType === "resolve_incident" && (!action.rootCause || !action.fix)) {
    throw new Error("resolve_incident requires root_cause and fix.");
  }
  if (action.actionType === "escalate" && !action.reason) {
    throw new Error("escalate requires a reason.");
  }
}

function formatAction(action: Action): string {
  switch (action.actionType) {
    case "inspect_logs":
    case "inspect_metrics":
    case "check_status":
    case "restart_service":
      return `${action.actionType}(${action.service})`;
    case "inspect_config":
      return action.key
        ? `inspect_config(${action.service}, ${action.key})`
        : `inspect_config(${action.service})`;
    case "update_config":
      return `update_config(${action.service}, ${action.key}, ${String(action.value)})`;
    case "resolve_incident":
      return `resolve_incident(${action.rootCause}, ${action.fix})`;
    case "escalate":
      return `escalate(${action.reason})`;
  }
}

function splitArgs(value: string): string[] {
  if (!value.trim()) {
    return [];
  }
  return value
    .split(",")
    .map((item) => stripQuotes(item.trim()))
    .filter((item) => item.length > 0);
}

function stripQuotes(value: string): string {
  if (value.length >= 2 && value[0] === value.at(-1) && (value[0] === "'" || value[0] === '"')) {
    return value.slice(1, -1);
  }
  return value;
}

function coerceValue(value: string): ConfigValue {
  if (value.toLowerCase() === "true") {
    return true;
  }
  if (value.toLowerCase() === "false") {
    return false;
  }
  const numeric = Number(value);
  return Number.isNaN(numeric) ? value : numeric;
}

function initialMetrics(): EpisodeMetrics {
  return {
    totalSteps: 0,
    invalidActions: 0,
    repeatedActions: 0,
    evidenceActions: 0,
    remediationActions: 0,
    wrongRemediations: 0,
    distractorFailures: 0,
    prematureResolutions: 0,
    success: false,
    finalReward: 0
  };
}

function requireField<T>(value: T | undefined, message: string): T {
  if (value === undefined) {
    throw new Error(message);
  }
  return value;
}

function isServiceName(value: string): value is ServiceName {
  return SERVICES.includes(value as ServiceName);
}

function normalizeText(value: string): string {
  return value.toLowerCase().replaceAll("_", " ").replaceAll("-", " ").replace(/\s+/g, " ").trim();
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function stringField(value: unknown, message: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(message);
  }
  return value;
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
