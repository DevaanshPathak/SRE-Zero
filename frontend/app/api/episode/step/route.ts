import { NextResponse } from "next/server";
import { getSession, type JsonAction } from "@/lib/simulator";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as {
    sessionId?: string;
    action?: unknown;
    rawAction?: string;
  };
  if (!body.sessionId) {
    return NextResponse.json({ error: "Missing sessionId." }, { status: 400 });
  }
  const session = getSession(body.sessionId);
  if (!session) {
    return NextResponse.json({ error: "Unknown or expired session." }, { status: 404 });
  }
  const action = body.rawAction && body.rawAction.trim() ? body.rawAction : body.action;
  if (!action) {
    return NextResponse.json({ error: "Missing action." }, { status: 400 });
  }
  return NextResponse.json(session.step(action as JsonAction));
}
