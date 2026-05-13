import { NextResponse } from "next/server";
import { loadModelCatalog } from "@/lib/modelConfig";

export const dynamic = "force-dynamic";

export function GET() {
  try {
    return NextResponse.json(loadModelCatalog());
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
