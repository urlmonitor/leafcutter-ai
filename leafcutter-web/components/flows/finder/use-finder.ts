"use client";

import { useCallback, useMemo, useState } from "react";
import type { MouseEvent } from "react";
import { buildFinderHref, normalizeQ, parseFinderQuery, toggleValue } from "@/lib/flow-finder/address";
import { runFinder } from "@/lib/flow-finder/run-finder";
import type { FacetName, FinderIndex, FinderRun, FinderState } from "@/lib/flow-finder/types";

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
}

/**
 * The finder's client state. Every edit recomputes from the index the page sent
 * (no server request) and rewrites the address in place with history.replaceState:
 * never a new history entry, never a router navigation.
 */
export function useFinder(index: FinderIndex, initial: FinderState): Finder {
  const [state, setState] = useState(initial);
  const [qText, setQText] = useState(initial.q ?? "");
  const run = useMemo(() => runFinder(index, state), [index, state]);

  const commit = useCallback((next: FinderState) => {
    setState(next);
    window.history.replaceState(window.history.state, "", buildFinderHref(next));
  }, []);

  const setQuery = (text: string) => {
    setQText(text);
    commit({ q: normalizeQ(text), facets: state.facets });
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

  return { state, qText, run, setQuery, toggle, followHref, inPlace };
}

