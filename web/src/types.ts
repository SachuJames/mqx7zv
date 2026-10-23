export interface HourPoint {
  startTime: string
  hourUtc: number
  forecast: number
  actual: number
  error: number
  publishTime: string
  horizonHours: number
  corrected: number
  bandLow: number
  bandHigh: number
}

export interface EvolutionPoint {
  publishTime: string
  meanForecast: number
  hourly: number[]
}

export interface ErrorStats {
  n: number
  mae: number | null
  rmse: number | null
  bias: number | null
  pctOver: number | null
}

export interface DayDetail {
  date: string
  decisionDate: string
  cutoff: string
  hours: HourPoint[]
  evolution: EvolutionPoint[]
  stats: ErrorStats
  shortfallMwh: number
  surplusMwh: number
  takeaway: string
}

export interface DaySummary {
  date: string
  decisionDate: string
  mae: number
  bias: number
  pctOver: number
  meanForecast: number
  meanActual: number
}

export interface Summary {
  stats: ErrorStats
  meanForecast: number
  meanActual: number
  errorQuantiles: { p10: number; p90: number }
  biasCorrectedMae: number
  byHorizon: ({ bucket: string } & ErrorStats)[]
  byHourOfDay: ({ hourUtc: number } & ErrorStats)[]
  distribution: { binStart: number; count: number }[]
  worstDays: { date: string; mae: number; bias: number }[]
  persistence: ErrorStats
  skillVsPersistence: number
  totalShortfallMwh: number
  totalSurplusMwh: number
}
