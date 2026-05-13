import { NextResponse } from "next/server";
import { listTasks, loadSplits } from "@/lib/simulator";

export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json({
    tasks: listTasks(),
    splits: loadSplits()
  });
}

