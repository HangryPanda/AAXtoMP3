import { NextResponse } from "next/server";

export async function GET() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  try {
    // Try to reach the backend
    const response = await fetch(`${apiUrl}/health`, {
      cache: "no-store",
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json({
        status: "ok",
        frontend: "healthy",
        backend: data,
      });
    }

    return NextResponse.json(
      {
        status: "degraded",
        frontend: "healthy",
        backend: "unhealthy",
        error: `Backend returned ${response.status}`,
      },
      { status: 200 }
    );
  } catch (error) {
    return NextResponse.json(
      {
        status: "degraded",
        frontend: "healthy",
        backend: "unreachable",
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 200 }
    );
  }
}
