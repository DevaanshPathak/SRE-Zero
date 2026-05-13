import fs from "node:fs";
import path from "node:path";
import type { ModelRunResult, Observation, TimelineItem } from "./types";
import { createEpisode } from "./simulator";

interface EnvConfig {
  apiKey: string;
  baseUrl: string;
  model: string;
  timeoutSeconds: number;
  temperature: number;
}

interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

const repoRoot = findRepoRoot(process.cwd());
const envPath = path.join(repoRoot, ".env");
const modelsPath = path.join(repoRoot, "notes", "available_models.md");
const modelLinePattern = /^~?[a-z0-9][a-z0-9-]*\/[a-z0-9][a-z0-9._:-]*$/i;
const actionPattern =
  /(inspect_logs|inspect_metrics|check_status|inspect_config|restart_service|update_config|resolve_incident|escalate)\s*\([^\n\r]*\)/i;

export function loadModelCatalog(): { models: string[]; currentModel: string | null; hasApiKey: boolean } {
  const env = loadEnvConfig();
  const models = new Set<string>();
  if (env.model) {
    models.add(env.model);
  }
  if (fs.existsSync(modelsPath)) {
    for (const line of fs.readFileSync(modelsPath, "utf-8").split(/\r?\n/)) {
      const candidate = line.trim();
      if (modelLinePattern.test(candidate)) {
        models.add(candidate);
      }
    }
  }
  return {
    models: [...models].sort((left, right) => left.localeCompare(right)),
    currentModel: env.model || null,
    hasApiKey: Boolean(env.apiKey)
  };
}

export async function runModelComparison(
  taskId: string,
  models: string[]
): Promise<ModelRunResult[]> {
  if (models.length !== 2) {
    throw new Error("Comparison requires exactly two models.");
  }
  const uniqueModels = [...new Set(models)];
  if (uniqueModels.length !== 2) {
    throw new Error("Choose two different models.");
  }
  const results: ModelRunResult[] = [];
  for (const model of uniqueModels) {
    results.push(await runPromptingBaseline(taskId, model));
  }
  return results;
}

async function runPromptingBaseline(taskId: string, model: string): Promise<ModelRunResult> {
  const env = loadEnvConfig(model);
  const episode = createEpisode(taskId);
  let observation = episode.initialObservation();
  const trajectory: TimelineItem[] = [];
  let terminalReason: string | null = null;
  let evidenceCoverage = 0;

  try {
    while (!observation.done) {
      const action = await chooseAction(env, observation);
      const result = episode.step(action);
      observation = result.observation;
      terminalReason = result.info.terminalReason ?? null;
      evidenceCoverage = result.info.evidenceCoverage;
      trajectory.push({
        step: observation.step,
        action: observation.lastAction ?? "",
        reward: result.reward,
        summary: observation.lastResult.summary,
        error: observation.lastResult.error
      });
    }

    return {
      model,
      success: episode.metrics.success,
      finalReward: episode.metrics.finalReward,
      totalSteps: episode.metrics.totalSteps,
      invalidActions: episode.metrics.invalidActions,
      evidenceCoverage,
      terminalReason,
      error: null,
      trajectory
    };
  } catch (error) {
    return {
      model,
      success: false,
      finalReward: episode.metrics.finalReward,
      totalSteps: episode.metrics.totalSteps,
      invalidActions: episode.metrics.invalidActions,
      evidenceCoverage,
      terminalReason,
      error: error instanceof Error ? error.message : String(error),
      trajectory
    };
  }
}

async function chooseAction(env: EnvConfig, observation: Observation): Promise<string> {
  const response = await chatComplete(env, [
    {
      role: "system",
      content:
        "You are running SRE-Zero, a simulated incident-response benchmark. " +
        "Use only the available simulator actions. Gather evidence before remediation. " +
        "Return exactly one action call and no extra text."
    },
    {
      role: "user",
      content:
        "Choose the next action for this observation.\n" +
        JSON.stringify(observation, null, 2) +
        "\n\nValid services: web_server, database, cache."
    }
  ]);
  return extractAction(response);
}

async function chatComplete(env: EnvConfig, messages: ChatMessage[]): Promise<string> {
  if (!env.baseUrl) {
    throw new Error("OPENAI_BASE_URL is missing in .env.");
  }
  if (!env.model) {
    throw new Error("OPENAI_MODEL is missing in .env or model selection.");
  }
  const endpoint = `${normalizeBaseUrl(env.baseUrl).replace(/\/$/, "")}/chat/completions`;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (env.apiKey) {
    headers.Authorization = `Bearer ${env.apiKey}`;
  }

  const response = await fetch(endpoint, {
    method: "POST",
    headers,
    body: JSON.stringify({
      model: env.model,
      messages,
      temperature: env.temperature,
      max_tokens: 220
    }),
    signal: AbortSignal.timeout(Math.round(env.timeoutSeconds * 1000))
  });
  const body = (await response.json().catch(() => ({}))) as {
    choices?: Array<{ message?: { content?: string } }>;
    error?: { message?: string };
  };
  if (!response.ok) {
    throw new Error(body.error?.message ?? `Provider returned HTTP ${response.status}`);
  }
  const content = body.choices?.[0]?.message?.content;
  if (!content) {
    throw new Error("Provider response did not include message content.");
  }
  return content.trim();
}

function extractAction(response: string): string {
  for (const line of response.trim().split(/\r?\n/).reverse()) {
    const match = line.match(actionPattern);
    if (match) {
      return match[0].trim();
    }
  }
  const match = response.match(actionPattern);
  if (match) {
    return match[0].trim();
  }
  return response.trim();
}

function loadEnvConfig(modelOverride?: string): EnvConfig {
  const values = readEnvFile();
  return {
    apiKey: values.OPENAI_API_KEY ?? "",
    baseUrl: values.OPENAI_BASE_URL ?? "",
    model: modelOverride ?? values.OPENAI_MODEL ?? "",
    timeoutSeconds: numberValue(values.SREZERO_LLM_TIMEOUT_SECONDS, 60),
    temperature: numberValue(values.SREZERO_LLM_TEMPERATURE, 0)
  };
}

function readEnvFile(): Record<string, string> {
  const values: Record<string, string> = {};
  if (!fs.existsSync(envPath)) {
    return values;
  }
  for (const rawLine of fs.readFileSync(envPath, "utf-8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) {
      continue;
    }
    const [key, ...rest] = line.split("=");
    values[key.trim()] = stripQuotes(rest.join("=").trim());
  }
  return values;
}

function findRepoRoot(start: string): string {
  let current = path.resolve(start);
  for (let depth = 0; depth < 4; depth += 1) {
    if (fs.existsSync(path.join(current, "pyproject.toml")) && fs.existsSync(path.join(current, "srezero"))) {
      return current;
    }
    const parent = path.dirname(current);
    if (parent === current) {
      break;
    }
    current = parent;
  }
  return path.resolve(start, "..");
}

function normalizeBaseUrl(baseUrl: string): string {
  if (/^https?:\/\//i.test(baseUrl)) {
    return baseUrl;
  }
  return `https://${baseUrl}`;
}

function stripQuotes(value: string): string {
  if (value.length >= 2 && value[0] === value.at(-1) && (value[0] === "'" || value[0] === '"')) {
    return value.slice(1, -1);
  }
  return value;
}

function numberValue(value: string | undefined, fallback: number): number {
  if (!value) {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}
