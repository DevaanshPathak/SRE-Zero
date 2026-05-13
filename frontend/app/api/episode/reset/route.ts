import { NextResponse } from "next/server";
import { createEpisode, saveSession } from "@/lib/simulator";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { taskId?: string };
  const taskId = body.taskId ?? "cache_crash";
  try {
    const session = createEpisode(taskId);
    saveSession(session);
    return NextResponse.json({
      sessionId: session.sessionId,
      observation: session.initialObservation(),
      info: {
        taskId,
        availableActions: session.initialObservation().availableTools
      }
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 400 }
    );
  }
}

