/**
 * Next.js Route Handler – SSE streaming proxy for patient analysis.
 *
 * Why a proxy?
 * 1. Avoids CORS issues: browser → same-origin → backend (server-side fetch).
 * 2. Vercel streaming functions get 60s timeout (vs 10s for regular functions).
 * 3. Works on both local and deployment without any extra env var config.
 *
 * The handler fetches from the backend's SSE endpoint and pipes the
 * text/event-stream body directly to the browser.
 */

export const runtime = "nodejs";
export const maxDuration = 60; // 60s for Vercel Hobby streaming

export async function GET() {
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8000/api";
  const streamUrl = `${backendUrl}/dashboard/stream`;

  try {
    const upstream = await fetch(streamUrl, {
      headers: { Accept: "text/event-stream" },
      // @ts-expect-error – Node 18+ fetch supports signal; prevent caching
      cache: "no-store",
    });

    if (!upstream.ok || !upstream.body) {
      return new Response(
        JSON.stringify({ error: "Backend streaming endpoint unavailable", status: upstream.status }),
        { status: 502, headers: { "Content-Type": "application/json" } }
      );
    }

    // Pipe the upstream SSE body directly to the client
    return new Response(upstream.body as ReadableStream, {
      status: 200,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err) {
    console.error("[stream proxy] Failed to connect to backend:", err);
    return new Response(
      JSON.stringify({ error: "Failed to connect to backend for streaming" }),
      { status: 502, headers: { "Content-Type": "application/json" } }
    );
  }
}
