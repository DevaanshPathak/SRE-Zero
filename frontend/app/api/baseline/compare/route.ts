import { NextResponse } from "next/server";
import { runModelComparison } from "@/lib/modelConfig";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as {
    taskId?: string;
    modelA?: string;
    modelB?: string;
  };
  if (!body.taskId || !body.modelA || !body.modelB) {
    return NextResponse.json(
      { error: "taskId, modelA, and modelB are required." },
      { status: 400 }
    );
  }
  try {
    const results = await runModelComparison(body.taskId, [body.modelA, body.modelB]);
    return NextResponse.json({ taskId: body.taskId, results });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 400 }
    );
  }
}
