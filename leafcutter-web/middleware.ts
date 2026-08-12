/**
 * Mock-mode middleware — UXP-553 runtime override.
 *
 * Resolves the effective mock override from the ?mock query-param and the
 * "mock" cookie, then:
 *   1. Persists the resolved state as a cookie (for future requests).
 *   2. Forwards it as the request header x-mock-active (for the CURRENT request).
 *
 * This two-step approach lets isMockActive() in mock.ts read the resolved value
 * immediately (via headers()) on the same request that set the cookie. Without
 * the request header, the cookie would only take effect on the next request.
 *
 * Query param takes precedence over cookie:
 *   ?mock=1  → resolves to "1"  (mock on)
 *   ?mock=0  → resolves to "0"  (mock off)
 *   (absent) → reads from the "mock" cookie (or resolves to null if no cookie)
 *
 * The production lock (LEAFCUTTER_MOCK_LOCK=real) takes highest priority:
 * when set, this middleware clears any stale mock cookie and forwards "0" so
 * the server always resolves to real data.
 */

import { NextRequest, NextResponse } from "next/server";

export function middleware(request: NextRequest): NextResponse {
  // Production lock: ignore all overrides, clear stale mock cookie.
  if (process.env.LEAFCUTTER_MOCK_LOCK === "real") {
    const reqHeaders = new Headers(request.headers);
    reqHeaders.set("x-mock-active", "0");
    const response = NextResponse.next({ request: { headers: reqHeaders } });
    response.cookies.delete("mock");
    return response;
  }

  const mockParam = request.nextUrl.searchParams.get("mock");
  const mockCookie = request.cookies.get("mock")?.value ?? null;

  // Query param takes precedence; fall back to cookie; null means "no override".
  const resolved: string | null =
    mockParam !== null ? (mockParam === "1" ? "1" : "0") :
    mockCookie !== null ? (mockCookie === "1" ? "1" : "0") :
    null;

  // Forward the resolved override as a request header so isMockActive() sees it
  // in the SAME request (cookies set on the response only arrive on the next request).
  const reqHeaders = new Headers(request.headers);
  if (resolved !== null) {
    reqHeaders.set("x-mock-active", resolved);
  } else {
    reqHeaders.delete("x-mock-active");
  }

  const response = NextResponse.next({ request: { headers: reqHeaders } });

  // Persist the resolved override as a sticky cookie so future no-query requests
  // remember the chosen mode.
  //
  // IMPORTANT: when mockParam is "0" we MUST set cookie "mock"="0" (not delete it).
  // Deleting the cookie makes the next request (with no ?mock) find no cookie,
  // fall through to the env default (LEAFCUTTER_MOCK=1), and flip back to mock —
  // breaking the "real" session the user just requested.
  //
  // Both "1" and "0" are sticky: ?mock=0 sets "mock"="0"; ?mock=1 sets "mock"="1".
  // The only way to clear the override is an explicit ?mock= (empty/unknown value,
  // which maps to "0"), or the production lock clearing it on every request.
  if (mockParam !== null) {
    response.cookies.set("mock", resolved ?? "0", {
      path: "/",
      httpOnly: true,
      sameSite: "lax",
    });
  }

  return response;
}

// Apply to all routes except Next.js internals and static assets.
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico).*)"],
};
