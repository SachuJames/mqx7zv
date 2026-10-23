import { useState } from 'react'
import AccuracyView from './AccuracyView'
import DecisionView from './DecisionView'
import './App.css'

type View = 'decision' | 'accuracy'

export default function App() {
  const [view, setView] = useState<View>('decision')

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Day-ahead wind: what the desk knew, and how it held up</h1>
          <p className="subtitle">
            National wind generation forecasts at the moment of the buying
            decision, scored against what was actually generated. UK, decisions
            made in January 2026.
          </p>
        </div>
        <nav className="tabs">
          <button
            className={view === 'decision' ? 'tab active' : 'tab'}
            onClick={() => setView('decision')}
          >
            Decision view
          </button>
          <button
            className={view === 'accuracy' ? 'tab active' : 'tab'}
            onClick={() => setView('accuracy')}
          >
            Forecast accuracy
          </button>
        </nav>
      </header>
      <main>{view === 'decision' ? <DecisionView /> : <AccuracyView />}</main>
      <footer className="footer">
        Data: Elexon BMRS, FUELHH (actual wind generation) and WINDFOR (wind
        generation forecast). Decision-time only: no forecast published after
        the 09:50 GMT day-ahead gate closure is used anywhere in this app.
      </footer>
    </div>
  )
}
