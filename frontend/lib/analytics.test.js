import { describe, it, expect, beforeEach } from 'vitest';
import { analyticsOptedOut, setAnalyticsOptOut } from './analytics';

describe('analytics opt-out (Phase 4b)', () => {
  beforeEach(() => { localStorage.clear(); });

  it('defaults to opted-in', () => {
    expect(analyticsOptedOut()).toBe(false);
  });

  it('setAnalyticsOptOut(true) opts out; false clears it', () => {
    setAnalyticsOptOut(true);
    expect(analyticsOptedOut()).toBe(true);
    expect(localStorage.getItem('dv_analytics_optout')).toBe('1');
    setAnalyticsOptOut(false);
    expect(analyticsOptedOut()).toBe(false);
    expect(localStorage.getItem('dv_analytics_optout')).toBe(null);
  });

  it('honours Global Privacy Control', () => {
    Object.defineProperty(navigator, 'globalPrivacyControl', { value: true, configurable: true });
    expect(analyticsOptedOut()).toBe(true);
    delete navigator.globalPrivacyControl;
  });
});
