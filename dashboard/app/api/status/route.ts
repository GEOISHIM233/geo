import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    status: "ok",
    message: "Bezms Dashboard API is online",
    timestamp: new Date().toISOString(),
  });
}
