"use client";

import { useEffect, useState } from "react";

export function useIsMobile(breakpoint = 640): boolean {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    // matchMedia, not window.innerWidth: on phones innerWidth grows when the
    // page overflows horizontally (the browser zooms out to fit it), so a
    // too-wide first desktop render would keep reporting "not mobile" and
    // lock the layout in desktop mode. Media queries use the device width.
    const mq = window.matchMedia(`(max-width: ${breakpoint - 1}px)`);
    const check = () => setIsMobile(mq.matches);
    check();
    mq.addEventListener("change", check);
    return () => mq.removeEventListener("change", check);
  }, [breakpoint]);
  return isMobile;
}
