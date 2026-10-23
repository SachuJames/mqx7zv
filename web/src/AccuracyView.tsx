import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { fetchSummary, fmtMw, fmtSignedMw } from './api'
import type { Summary } from './types'

export default function AccuracyView() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [error, setError] = useState<string>('')

  useEffect(() => {
    fetchSummary()
      .then(setSummary)
      .catch(() => setError('Could not load the accuracy summary from the API.'))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!summary) return <p className="loading">Loading accuracy data...</p>

  const s = summary.stats
  const skillPct = Math.round((summary.skillVsPersistence ?? 0) * 100)

  return (
    <div>
      <div className="cards">
        <div className="card">
          <span className="card-label">MAE</span>
          <strong>{fmtMw(s.mae)}</strong>
          <span className="card-sub">across {s.n} delivery hours</span>
        </div>
        <div className="card">
          <span className="card-label">RMSE</span>
          <strong>{fmtMw(s.rmse)}</strong>
          <span className="card-sub">penalises the big misses</span>
        </div>
        <div className="card">
          <span className="card-label">Bias</span>
          <strong>{fmtSignedMw(s.bias)}</strong>
          <span className="card-sub">systematic over-forecast</span>
        </div>
        <div className="card">
          <span className="card-label">Hours over-forecast</span>
          <strong>{s.pctOver}%</strong>
          <span className="card-sub">of January delivery hours</span>
        </div>
        <div className="card">
          <span className="card-label">Skill vs persistence</span>
          <strong>{skillPct}%</strong>
          <span className="card-sub">
            persistence MAE {fmtMw(summary.persistence.mae)}
          </span>
        </div>
        <div className="card">
          <span className="card-label">MAE if bias removed</span>
          <strong>{fmtMw(summary.biasCorrectedMae)}</strong>
          <span className="card-sub">the cost of the bias, in accuracy terms</span>
        </div>
      </div>

      <p className="takeaway">
        Buying on the raw forecast left the desk roughly{' '}
        {summary.totalShortfallMwh.toLocaleString('en-GB')} MWh short across January,
        energy that had to be covered later at balancing prices, against{' '}
        {summary.totalSurplusMwh.toLocaleString('en-GB')} MWh bought but not needed.
      </p>

      <div className="grid-2">
        <section className="panel">
          <h2>Error by forecast horizon</h2>
          <p className="panel-note">
            Hours further from the decision were not the problem in January: the
            bias is already present at the shortest horizons.
          </p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart
              data={summary.byHorizon.map((b) => ({ name: b.bucket, mae: b.mae, bias: b.bias }))}
              margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
            >
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip formatter={(value: unknown) => fmtMw(typeof value === 'number' ? value : null)} />
              <Bar dataKey="mae" name="MAE" fill="#2563eb" />
              <Bar dataKey="bias" name="Bias" fill="#b45309" />
            </BarChart>
          </ResponsiveContainer>
        </section>

        <section className="panel">
          <h2>Error by hour of day (GMT)</h2>
          <p className="panel-note">
            Bias by settlement hour. The morning ramp hours carry some of the
            largest over-forecasts.
          </p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart
              data={summary.byHourOfDay.map((h) => ({
                name: `${String(h.hourUtc).padStart(2, '0')}:00`,
                mae: h.mae,
                bias: h.bias,
              }))}
              margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
            >
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={2} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip formatter={(value: unknown) => fmtMw(typeof value === 'number' ? value : null)} />
              <Bar dataKey="mae" name="MAE" fill="#2563eb" />
              <Bar dataKey="bias" name="Bias" fill="#b45309" />
            </BarChart>
          </ResponsiveContainer>
        </section>
      </div>

      <div className="grid-2">
        <section className="panel">
          <h2>Error distribution</h2>
          <p className="panel-note">
            Signed error per hour (forecast minus actual), in 1,000 MW bins. The
            whole distribution sits to the right of zero, which is the bias made
            visible. 80% of hours fell between {fmtSignedMw(summary.errorQuantiles.p10)}{' '}
            and {fmtSignedMw(summary.errorQuantiles.p90)}.
          </p>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart
              data={summary.distribution.map((b) => ({
                name: `${(b.binStart / 1000).toFixed(0)}k`,
                count: b.count,
              }))}
              margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
            >
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="count" name="Hours" fill="#0f766e" />
            </BarChart>
          </ResponsiveContainer>
        </section>

        <section className="panel">
          <h2>Worst days</h2>
          <p className="panel-note">Settlement days ranked by decision-time MAE.</p>
          <table>
            <thead>
              <tr>
                <th>Settlement day</th>
                <th>MAE</th>
                <th>Bias</th>
              </tr>
            </thead>
            <tbody>
              {summary.worstDays.map((d) => (
                <tr key={d.date}>
                  <td>{d.date}</td>
                  <td>{fmtMw(d.mae)}</td>
                  <td>{fmtSignedMw(d.bias)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      <section className="panel methodology">
        <h2>Methodology</h2>
        <p>
          Scope is purchase decisions made in January 2026, read literally: decision
          days 1 to 31 January, buying for settlement days 2 January to 1 February.
          A settlement day runs 23:00 GMT to 23:00 GMT. For each settlement day, the
          decision forecast is the last WINDFOR forecast published at or before the
          N2EX day-ahead gate closure at 09:50 GMT on the day before, in practice
          the 09:30 GMT publish. Forecasts published after the gate closed are
          excluded from every number on this page, including the band and the bias
          correction, so nothing here uses information the desk did not have when
          it committed. Actuals are FUELHH wind generation, averaged from
          half-hourly to hourly to match the forecast resolution. Persistence
          means using the previous day's actual at the same hour as the forecast.
        </p>
      </section>
    </div>
  )
}
