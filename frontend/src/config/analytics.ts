// Analytics configuration

/** The periods the trend charts can be read in. */
export type AnalyticsPeriod = 'daily' | 'weekly' | 'monthly'

/**
 * How far back each trend chart window reaches, per period.
 *
 * This is the knob for widening the window: raise a number and the chart adds
 * older periods, filled with a zero wherever nothing happened. Nothing else has
 * to change, but three things are worth knowing before raising one:
 *
 * - It costs no extra requests. The page loads every review the filters match
 *   either way, because the aggregation runs in the browser; the window only
 *   decides how much of that is drawn.
 * - The axis is a fixed width, so ECharts thins the labels rather than showing
 *   them all. Much past a few dozen points a series is read as a shape rather
 *   than as values.
 * - The window ends at the current period, not at the newest review, so a window
 *   longer than the recorded history ends in a flat run of zeros.
 *
 * The charts that share the period selector share this window, so they stay on
 * one axis.
 */
export const ANALYTICS_PERIOD_WINDOWS: Record<AnalyticsPeriod, number> = {
  daily: 180,
  weekly: 26,
  monthly: 6,
}
