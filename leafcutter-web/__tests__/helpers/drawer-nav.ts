/**
 * Shared harness for the UXP-591-4 / UXP-591-2-ii drawer-navigation tests.
 * Not a test file (no .test suffix). Each test file must declare the same
 * vi.mock calls for next/headers and next/navigation; the hoisted router
 * spies and header store are passed in here.
 */
import { expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { addressOf, forwardedHeaders, load, paramsFor, runMiddleware, searchParamsOf } from "./flow-routes";

export interface NavState {
  headers: Headers;
  routerPush: ReturnType<typeof vi.fn>;
  routerReplace: ReturnType<typeof vi.fn>;
}

/** Put the tab at `url` as the App Router would leave it (history.state carries its own keys). */
export function placeTabAt(url: string) {
  window.history.replaceState(
    { __NA: true, __PRIVATE_NEXTJS_INTERNALS_TREE: ["", {}] },
    "",
    url,
  );
}

/** Open an address: tab placed at it, middleware run, then the real route page rendered. */
export async function openAt(nav: NavState, url: string) {
  placeTabAt(url);
  if (url === "/flows" || url.startsWith("/flows?")) {
    const mod = await load("@/app/flows/page");
    return render(await mod.default({ searchParams: searchParamsOf(`http://localhost${url}`) }));
  }
  const abs = `http://localhost${url}`;
  nav.headers = forwardedHeaders(await runMiddleware(abs));
  const mod = await load("@/app/flows/[...id]/page");
  return render(await mod.default({ params: paramsFor(abs), searchParams: searchParamsOf(abs) }));
}

export function watchHistory(nav: NavState) {
  nav.routerPush.mockClear();
  nav.routerReplace.mockClear();
  return {
    length: window.history.length,
    replace: vi.spyOn(window.history, "replaceState"),
    push: vi.spyOn(window.history, "pushState"),
  };
}

/** Exactly `writes` replaceState calls, the last to `address`; no entry added anywhere. */
export function expectReplaced(
  nav: NavState,
  w: ReturnType<typeof watchHistory>,
  address: string,
  writes = 1,
) {
  expect(w.replace).toHaveBeenCalledTimes(writes);
  expect(addressOf(w.replace.mock.calls[writes - 1][2])).toBe(address);
  expect(w.push).not.toHaveBeenCalled();
  expect(nav.routerPush).not.toHaveBeenCalled();
  expect(nav.routerReplace).not.toHaveBeenCalled();
  expect(window.history.length).toBe(w.length);
  expect(window.location.pathname + window.location.search).toBe(address);
}
