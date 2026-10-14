"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent } from "react";
import { buildFinderHref, normalizeQ, parseFinderQuery, toggleValue } from "@/lib/flow-finder/address";
import { runFinder } from "@/lib/flow-finder/run-finder";
import type { FacetName, FinderIndex, FinderRun, FinderState } from "@/lib/flow-finder/types";

/** Typing writes the address once, this long after the last keystroke. */
export const ADDRESS_WRITE_DELAY_MS = 250;

export interface Finder {
  state: FinderState;
  /** The search box text as typed (untrimmed); the address keeps the trimmed q. */
  qText: string;
  run: FinderRun;
  setQuery: (text: string) => void;
  toggle: (facet: FacetName, value: string) => void;
  /** Follow a finder address in place (chip remove, Clear all, empty-state suggestion). */
  followHref: (href: string) => void;
  /** onClick for a finder link: a plain click edits in place, a modified click opens normally. */
  inPlace: (href: string) => (e: MouseEvent<HTMLAnchorElement>) => void;
  /** Write a pending (coalesced) address now. Call before any push. */
  flush: () => void;
}

/**
 * The finder's client state. Every edit recomputes from the index the page sent
 * (no server request) and rewrites the address in place with history.replaceState:
 * never a new history entry, never a router navigation. Typing coalesces into one
 * write after the last keystroke; a facet edit writes at once.
 */
export function useFinder(index: FinderIndex, initial: FinderState): Finder {
  const [state, setState] = useState(initial);
  const [qText, setQText] = useState(initial.q ?? "");
  const run = useMemo(() => runFinder(index, state), [index, state]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef<string | null>(null);

  const cancel = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    pending.current = null;
  };
  const write = (href: string) => {
    cancel();
    window.history.replaceState(window.history.state, "", href);
  };
  const flush = useCallback(() => {
    const href = pending.current;
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    pending.current = null;
    if (href !== null) window.history.replaceState(window.history.state, "", href);
  }, []);
  // Unmounting (a pushed flow, a pop) drops a write that was not flushed.
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const commit = (next: FinderState, coalesce = false) => {
    setState(next);
    const href = buildFinderHref(next);
    if (!coalesce) return write(href);
    pending.current = href;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(flush, ADDRESS_WRITE_DELAY_MS);
  };

  const setQuery = (text: string) => {
    setQText(text);
    commit({ q: normalizeQ(text), facets: state.facets }, true);
  };
  const toggle = (facet: FacetName, value: string) => commit(toggleValue(state, facet, value));
  const followHref = (href: string) => {
    const next = parseFinderQuery(new URL(href, window.location.origin).searchParams);
    setQText(next.q ?? "");
    commit(next);
  };
  const inPlace = (href: string) => (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    followHref(href);
  };

  return { state, qText, run, setQuery, toggle, followHref, inPlace, flush };
}
