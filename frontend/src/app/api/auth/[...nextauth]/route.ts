import { handlers } from "@/lib/auth/config";
import { normalizeAuthRequest } from "@/lib/auth/request-origin";
import { NextRequest } from "next/server";

async function handle(request: NextRequest) {
  const normalized = normalizeAuthRequest(request);
  if (!normalized) {
    return Response.json(
      { error: "untrusted_request_origin" },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }
  return request.method === "POST"
    ? handlers.POST(normalized)
    : handlers.GET(normalized);
}

export const GET = handle;
export const POST = handle;
