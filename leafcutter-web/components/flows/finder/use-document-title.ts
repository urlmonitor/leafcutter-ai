"use client";

import { useEffect } from "react";

/** Keep document.title in step with what the client shows (drills, Back/Forward, opened results). */
export function useDocumentTitle(title: string | null) {
  useEffect(() => {
    if (title !== null) document.title = title;
  }, [title]);
}
