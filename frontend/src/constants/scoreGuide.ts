export interface ScoreGrade {
  /** Stable id used for i18n keys (`tpl_${id}`), CSS types and built-in templates */
  id: 'excellent' | 'good' | 'acceptable' | 'needs_improvement' | 'poor'
  /** Grade label shown on quick buttons and in the guideline */
  label: string
  /** Inclusive lower bound of the 0-10 scale */
  min: number
  /** Inclusive upper bound of the 0-10 scale */
  max: number
  /** CSS class name used for colors (dash form) */
  className: string
  /** Score pre-selected when the grade quick button is clicked */
  quickValue: number
}

/**
 * Grades used to evaluate an AI code review result (0 - 10).
 *
 * The score is assigned by a human and measures how accurate, valuable and
 * actionable the AI review output for a PR is — NOT the code quality of the
 * PR itself. See ScoreRangeGuide for the full guideline.
 */
export const SCORE_GRADES: ScoreGrade[] = [
  {
    id: 'excellent',
    label: 'Excellent',
    min: 9.0,
    max: 10.0,
    className: 'excellent',
    quickValue: 9.5,
  },
  {
    id: 'good',
    label: 'Good',
    min: 7.0,
    max: 8.9,
    className: 'good',
    quickValue: 8.0,
  },
  {
    id: 'acceptable',
    label: 'Acceptable',
    min: 5.0,
    max: 6.9,
    className: 'acceptable',
    quickValue: 6.0,
  },
  {
    id: 'needs_improvement',
    label: 'Needs Improvement',
    min: 3.0,
    max: 4.9,
    className: 'needs-improvement',
    quickValue: 4.0,
  },
  {
    id: 'poor',
    label: 'Poor',
    min: 0.0,
    max: 2.9,
    className: 'poor',
    quickValue: 2.0,
  },
]

/** Return the grade that covers a given score value (0-10 scale). */
export function getScoreGrade(score: number): ScoreGrade | undefined {
  return SCORE_GRADES.find((grade) => score >= grade.min && score <= grade.max)
}
