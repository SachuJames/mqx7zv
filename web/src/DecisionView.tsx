import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fetchDay, fetchDays, fmtMw, fmtSignedMw, publishLabel, timeLabel } from './api'
import type { DayDetail, DaySummary } from './types'

export default function DecisionView() {
  const [days, setDays] = useState<DaySummary[]>([])
  const [selected, setSelected] = useState<string>('')
  const [day, setDay] = useState<DayDetail | null>(null)
  const [error, setError] = useState<string>('')

  useEffect(() => {
    fetchDays()
      .then((list) => {
        setDays(list)
        if (list.length) setSelected(list[list.length - 1].date)
      })
      .catch(() => setError('Could not load the day list from the API.'))
  }, [])

  useEffect(() => {
    if (!selected) return
    fetchDay(selected)
      .then(setDay)
      .catch(() => setError('Could not load that day from the API.'))
  }, [selected])

  const chartData = useMemo(
    () =>
      (day?.hours ?? []).map((h) => ({
        label: `${timeLabel(h.startTime)}`,
        forecast: h.forecast,
        actual: h.actual,
        corrected: h.corrected,
        band: [h.bandLow, h.bandHigh] as [number, number],
      })),
    [day],
  )

  const evolutionData = useMemo(
    () =>
      (day?.evolution ?? []).map((e) => ({
        label: publishLabel(e.publishTime),
        meanForecast: e.meanForecast,
      })),
    [day],
  )

  if (error) return <p className="error">{error}</p>
  if (!day) return <p className="loading">Loading decision data...</p>

  return (
    <div>
      <div className="toolbar">
        <label htmlFor="day-select">Settlement day</label>
        <select
          id="day-select"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          {days.map((d) => (
            <option key={d.date} value={d.date}>
              {d.date} (decided {d.decisionDate})
            </option>
          ))}
        </select>
        <span className="toolbar-note">
          Decision locked at the day-ahead gate closure, {timeLabel(day.cutoff)} GMT on{' '}
          {day.decisionDate}. Forecast shown is the last one published before that
          moment: {publishLabel(day.hours[0]?.publishTime ?? day.cutoff)} GMT.
        </span>
      </div>

      <p className="takeaway">{day.takeaway}</p>

      <div className="cards">
        <div className="card">
          <span className="card-label">Mean forecast</span>
          <strong>{fmtMw(chartData.reduce((a, c) => a + c.forecast, 0) / chartData.length)}</strong>
        </div>
        <div className="card">
          <span className="card-label">Mean actual</span>
          <strong>{fmtMw(chartData.reduce((a, c) => a + c.actual, 0) / chartData.length)}</strong>
        </div>
        <div className="card">
          <span className="card-label">Day MAE</span>
          <strong>{fmtMw(day.stats.mae)}</strong>
        </div>
        <div className="card">
          <span className="card-label">Day bias</span>
          <strong>{fmtSignedMw(day.stats.bias)}</strong>
        </div>
        <div className="card">
          <span className="card-label">Shortfall</span>
          <strong>{day.shortfallMwh.toLocaleString('en-GB')} MWh</strong>
        </div>
      </div>

      <section className="panel">
        <h2>What the desk saw vs what happened</h2>
        <p className="panel-note">
          The shaded band is built from January's own decision-time errors, 10th to
          90th percentile. Actual generation fell inside it in about 80% of January
          hours, which is true by construction: it describes January, and is not a
          promise about coverage on future days. The bias-corrected line takes the
          month's average over-forecast off the raw forecast. That correction is also
          worked out on the same January data it is applied to, so read it as an
          illustration of what removing the bias would have done. A live desk would
          correct using only errors from before the day, and would do a little worse.
        </p>
        <p className="panel-note">
          Shortfall is an energy amount, not a cost. It is the extra MWh the desk had
          to find because wind came in below the forecast it bought on. What that
          energy cost depends on balancing prices at the time, which are not in this
          dataset, so the app does not price it. The opposite case, wind beating the
          forecast, is surplus: power bought ahead that was not needed.
        </p>
        <ResponsiveContainer width="100%" height={360}>
          <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} interval={2} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => `${(v / 1000).toFixed(0)} GW`} />
            <Tooltip formatter={(value: unknown) => fmtMw(typeof value === 'number' ? value : null)} />
            <Area dataKey="band" name="January error band (P10-P90)" stroke="none" fill="#93c5fd" fillOpacity={0.35} />
            <Line dataKey="forecast" name="Forecast at decision time" stroke="#b45309" strokeWidth={2} dot={false} />
            <Line dataKey="corrected" name="Bias-corrected (illustrative)" stroke="#2563eb" strokeWidth={2} strokeDasharray="6 3" dot={false} />
            <Line dataKey="actual" name="Actual" stroke="#0f766e" strokeWidth={2.5} dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </section>

      <section className="panel">
        <h2>How the forecast moved before the gate closed</h2>
        <p className="panel-note">
          Mean forecast for this settlement day at each publish in the run-up to the
          decision. Publishes after the 09:50 GMT gate closure are excluded: the desk
          could not have used them.
        </p>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={evolutionData} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={1} />
            <YAxis tick={{ fontSize: 12 }} domain={['auto', 'auto']} tickFormatter={(v: number) => `${(v / 1000).toFixed(1)} GW`} />
            <Tooltip formatter={(value: unknown) => fmtMw(typeof value === 'number' ? value : null)} />
            <Line dataKey="meanForecast" name="Mean forecast for the day" stroke="#7c3aed" strokeWidth={2} dot={{ r: 2.5 }} />
          </LineChart>
        </ResponsiveContainer>
      </section>
    </div>
  )
}
