'use client';

import { useEffect } from 'react';
import { track } from '../lib/analytics';

// Fire a single analytics event on mount (1c). Drop into any page:
//   <Track event="landing_view" />
export default function Track({ event, props }) {
  useEffect(() => {
    track(event, props);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}
