import { useState, useEffect } from 'react'

const TABS = ['CHAMPIONS', 'DRIVERS', 'CONSTRUCTORS', 'CIRCUITS', 'HISTORY']

// ── Wikipedia slug lookup ────────────────────────────────────────────────────
const DRIVER_WIKI = {
  'Lewis Hamilton':       'Lewis_Hamilton',
  'Michael Schumacher':   'Michael_Schumacher',
  'Juan Manuel Fangio':   'Juan_Manuel_Fangio',
  'Alain Prost':          'Alain_Prost',
  'Sebastian Vettel':     'Sebastian_Vettel',
  'Max Verstappen':       'Max_Verstappen',
  'Ayrton Senna':         'Ayrton_Senna',
  'Jackie Stewart':       'Jackie_Stewart',
  'Niki Lauda':           'Niki_Lauda',
  'Nelson Piquet':        'Nelson_Piquet',
  'Alberto Ascari':       'Alberto_Ascari',
  'Graham Hill':          'Graham_Hill',
  'Jim Clark':            'Jim_Clark',
  'Emerson Fittipaldi':   'Emerson_Fittipaldi',
  'Mika Hakkinen':        'Mika_Häkkinen',
  'Fernando Alonso':      'Fernando_Alonso',
  'Jack Brabham':         'Jack_Brabham',
  'Nigel Mansell':        'Nigel_Mansell',
  'Kimi Raikkonen':       'Kimi_Räikkönen',
  'Jenson Button':        'Jenson_Button',
  'Damon Hill':           'Damon_Hill',
  'Jacques Villeneuve':   'Jacques_Villeneuve',
  'Nico Rosberg':         'Nico_Rosberg',
  'Gilles Villeneuve':    'Gilles_Villeneuve',
  'Carlos Reutemann':     'Carlos_Reutemann',
  'Stirling Moss':        'Stirling_Moss',
  'Charles Leclerc':      'Charles_Leclerc',
  'Lando Norris':         'Lando_Norris',
  'George Russell':       'George_Russell_(racing_driver)',
  'Carlos Sainz':         'Carlos_Sainz_Jr.',
  'Mick Schumacher':      'Mick_Schumacher',
}

const CONSTRUCTOR_WIKI = {
  'Ferrari':       'Scuderia_Ferrari',
  'McLaren':       'McLaren_Racing',
  'Williams':      'Williams_Racing',
  'Mercedes':      'Mercedes-AMG_Petronas_F1_Team',
  'Red Bull Racing': 'Red_Bull_Racing',
  'Lotus':         'Lotus_F1',
  'Brabham':       'Brabham',
  'Renault':       'Renault_in_Formula_One',
  'Benetton':      'Benetton_Formula',
  'Brawn':         'Brawn_GP',
  'Aston Martin':  'Aston_Martin_in_Formula_One',
  'Alpine':        'Alpine_F1_Team',
  'Haas':          'Haas_F1_Team',
  'Racing Bulls':  'RB_Formula_One_Team',
  'Sauber':        'Sauber_Motorsport',
  'Cooper':        'Cooper_Car_Company',
  'Alfa Romeo':    'Alfa_Romeo_in_Formula_One',
  'Tyrrell':       'Tyrrell_Racing',
}

// Maps circuit encyclopedia name → FastF1 EventName stored in MongoDB
const CIRCUIT_MAP_KEY = {
  'Autodromo Nazionale Monza':       'Italian Grand Prix',
  'Circuit de Monaco':               'Monaco Grand Prix',
  'Silverstone Circuit':             'British Grand Prix',
  'Circuit de Spa-Francorchamps':    'Belgian Grand Prix',
  'Autodromo Enzo e Dino Ferrari':   'Emilia Romagna Grand Prix',
  'Circuit de Catalunya':            'Spanish Grand Prix',
  'Red Bull Ring':                   'Austrian Grand Prix',
  'Hungaroring':                     'Hungarian Grand Prix',
  'Zandvoort':                       'Dutch Grand Prix',
  'Suzuka International Racing Course': 'Japanese Grand Prix',
  'Marina Bay Street Circuit':       'Singapore Grand Prix',
  'Shanghai International Circuit':  'Chinese Grand Prix',
  'Bahrain International Circuit':   'Bahrain Grand Prix',
  'Yas Marina Circuit':              'Abu Dhabi Grand Prix',
  'Jeddah Corniche Circuit':         'Saudi Arabian Grand Prix',
  'Losail International Circuit':    'Qatar Grand Prix',
  'Circuit of the Americas':         'United States Grand Prix',
  'Autodromo Hermanos Rodriguez':    'Mexico City Grand Prix',
  'Autodromo Jose Carlos Pace':      'São Paulo Grand Prix',
  'Circuit Gilles Villeneuve':       'Canadian Grand Prix',
  'Miami International Autodrome':   'Miami Grand Prix',
  'Las Vegas Strip Circuit':         'Las Vegas Grand Prix',
  'Albert Park Circuit':             'Australian Grand Prix',
}

// ── Hooks ────────────────────────────────────────────────────────────────────

function useWikiImage(slug) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    if (!slug) return
    setUrl(null)
    fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(slug)}`)
      .then(r => r.json())
      .then(d => setUrl(d.thumbnail?.source ?? null))
      .catch(() => {})
  }, [slug])
  return url
}

// ── Mini track map SVG ────────────────────────────────────────────────────────

function MiniTrackMap({ mapKey }) {
  const [points, setPoints] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!mapKey) return
    setLoading(true)
    setPoints(null)
    fetch(`/api/track-map/${encodeURIComponent(mapKey)}/`)
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(d => { setPoints(d.points ?? null); setLoading(false) })
      .catch(() => setLoading(false))
  }, [mapKey])

  if (loading) return <div className="modal-track-placeholder">LOADING MAP<span className="blink">...</span></div>
  if (!points || points.length < 2) return <div className="modal-track-placeholder">NO MAP DATA</div>

  const xs = points.map(p => p.x)
  const ys = points.map(p => p.y)
  const xMin = Math.min(...xs), xMax = Math.max(...xs)
  const yMin = Math.min(...ys), yMax = Math.max(...ys)
  const span = Math.max(xMax - xMin, yMax - yMin)
  const pad  = span * 0.08
  const vbX  = xMin - pad, vbY = yMin - pad
  const vbW  = (xMax - xMin) + pad * 2
  const vbH  = (yMax - yMin) + pad * 2
  const sw   = span * 0.018

  const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ')

  return (
    <svg viewBox={`${vbX} ${vbY} ${vbW} ${vbH}`} className="modal-track-svg">
      <path d={d} fill="none" stroke="var(--green)" strokeWidth={sw}
            strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function Encyclopedia() {
  const [tab, setTab]           = useState('CHAMPIONS')
  const [items, setItems]       = useState([])
  const [selected, setSelected] = useState(null)
  const [detail, setDetail]     = useState(null)

  useEffect(() => {
    const urls = {
      CHAMPIONS:    '/api/encyclopedia/champions/',
      DRIVERS:      '/api/encyclopedia/drivers/',
      CONSTRUCTORS: '/api/encyclopedia/constructors/',
      CIRCUITS:     '/api/encyclopedia/circuits/',
      HISTORY:      '/api/encyclopedia/history/',
    }
    setItems([])
    setSelected(null)
    setDetail(null)
    fetch(urls[tab]).then(r => r.json()).then(setItems).catch(() => {})
  }, [tab])

  const handleSelect = (item) => { setSelected(item); setDetail(item) }

  const renderLabel = (item) => {
    switch (tab) {
      case 'CHAMPIONS':    return <><em>{item.year}</em> {item.driver_champion} <span style={{color:'var(--cyan)'}}>{item.team}</span></>
      case 'DRIVERS':      return <><em>{item.championships}×</em> {item.name}</>
      case 'CONSTRUCTORS': return <><em>{item.constructor_titles}×</em> {item.name}</>
      case 'CIRCUITS':     return <><em>{item.country}</em> {item.name}</>
      case 'HISTORY':      return <><em>{item.years}</em> {item.era}</>
      default: return item.name
    }
  }

  return (
    <>
      <div className="encyclopedia-panel">
        <div className="enc-tabs">
          {TABS.map(t => (
            <button key={t} className={`enc-tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
              {t}
            </button>
          ))}
        </div>
        <div className="enc-scroll">
          {items.map((item, i) => (
            <div
              key={i}
              className={`enc-item ${selected === item ? 'selected' : ''}`}
              onClick={() => handleSelect(item)}
            >
              {renderLabel(item)}
            </div>
          ))}
        </div>
      </div>

      {detail && <DetailModal tab={tab} data={detail} onClose={() => setDetail(null)} />}
    </>
  )
}

// ── Detail modal ──────────────────────────────────────────────────────────────

function DetailModal({ tab, data, onClose }) {
  const isWide = tab === 'DRIVERS' || tab === 'CONSTRUCTORS' || tab === 'CIRCUITS'
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className={`modal ${isWide ? 'wide' : ''}`} onClick={e => e.stopPropagation()}>
        <div className="modal-title">
          <button className="modal-close" onClick={onClose}>✕ CLOSE</button>
          {tab === 'CHAMPIONS'    && `${data.year} — ${data.driver_champion}`}
          {tab === 'DRIVERS'      && data.name}
          {tab === 'CONSTRUCTORS' && (data.full_name ?? data.name)}
          {tab === 'CIRCUITS'     && data.name}
          {tab === 'HISTORY'      && `${data.years} — ${data.era}`}
        </div>

        {tab === 'CHAMPIONS'    && <ChampionDetail d={data} />}
        {tab === 'DRIVERS'      && <DriverDetail   d={data} />}
        {tab === 'CONSTRUCTORS' && <ConstructorDetail d={data} />}
        {tab === 'CIRCUITS'     && <CircuitDetail  d={data} />}
        {tab === 'HISTORY'      && <HistoryDetail  d={data} />}
      </div>
    </div>
  )
}

// ── Shared row component ──────────────────────────────────────────────────────

const Row = ({ label, value, className }) => value !== undefined && value !== null ? (
  <>
    <div className="modal-label">{label}</div>
    <div className={`modal-value ${className ?? ''}`}>{String(value)}</div>
  </>
) : null

// ── Detail bodies ─────────────────────────────────────────────────────────────

function ChampionDetail({ d }) {
  return (
    <div className="modal-grid">
      <Row label="YEAR"        value={d.year} className="champion" />
      <Row label="DRIVER"      value={d.driver_champion} />
      <Row label="TEAM"        value={d.team} />
      <Row label="CONSTRUCTOR" value={d.constructor_champion} />
      <div className="modal-label">NOTES</div>
      <div className="modal-bio">{d.notable}</div>
    </div>
  )
}

function DriverDetail({ d }) {
  const imgUrl = useWikiImage(DRIVER_WIKI[d.name])
  return (
    <div className={imgUrl ? 'modal-body-with-image' : ''}>
      <div>
        <div className="modal-grid">
          <Row label="NATIONALITY"   value={d.nationality} />
          <Row label="BORN"          value={d.born} />
          <Row label="CHAMPIONSHIPS" value={d.championships} className="champion" />
          <Row label="TITLES"        value={d.championship_years?.join(', ')} />
          <Row label="WINS"          value={d.wins} />
          <Row label="POLES"         value={d.poles} />
          <Row label="PODIUMS"       value={d.podiums} />
          <Row label="FASTEST LAPS"  value={d.fastest_laps} />
          <Row label="TEAMS"         value={d.teams?.join(' → ')} />
          <Row label="STATUS"        value={d.active ? '🟢 ACTIVE' : '⬛ RETIRED'} />
        </div>
        {d.bio && <div className="modal-bio">{d.bio}</div>}
      </div>
      {imgUrl && (
        <div className="modal-image-col">
          <img src={imgUrl} className="modal-side-image" alt={d.name} />
          <div className="modal-image-label">WIKIPEDIA</div>
        </div>
      )}
    </div>
  )
}

function ConstructorDetail({ d }) {
  const imgUrl = useWikiImage(CONSTRUCTOR_WIKI[d.name])
  return (
    <div className={imgUrl ? 'modal-body-with-image' : ''}>
      <div>
        <div className="modal-grid">
          <Row label="BASE"               value={d.base} />
          <Row label="FOUNDED"            value={d.founded} />
          <Row label="CONSTRUCTOR TITLES" value={d.constructor_titles} className="champion" />
          <Row label="DRIVER TITLES"      value={d.driver_titles} />
          <Row label="FIRST TITLE"        value={d.first_title} />
          <Row label="NOTABLE DRIVERS"    value={d.notable_drivers?.slice(0, 6).join(', ')} />
        </div>
        {d.bio && <div className="modal-bio">{d.bio}</div>}
      </div>
      {imgUrl && (
        <div className="modal-image-col">
          <img src={imgUrl} className="modal-side-image" alt={d.name} />
          <div className="modal-image-label">WIKIPEDIA</div>
        </div>
      )}
    </div>
  )
}

function CircuitDetail({ d }) {
  const mapKey = CIRCUIT_MAP_KEY[d.name]
  return (
    <div className="modal-body-with-image">
      <div>
        <div className="modal-grid">
          <Row label="LOCATION"   value={d.location} />
          <Row label="COUNTRY"    value={d.country} />
          <Row label="TYPE"       value={d.type?.toUpperCase()} />
          <Row label="LENGTH"     value={d.length_km ? `${d.length_km} km` : null} />
          <Row label="FIRST GP"   value={d.first_gp} />
          <Row label="GPs HELD"   value={d.gps_held} />
          <Row label="LAP RECORD" value={d.lap_record ? `${d.lap_record} — ${d.lap_record_holder} (${d.lap_record_year})` : null} className="champion" />
          <Row label="NICKNAME"   value={d.nickname} />
          <Row label="STATUS"     value={d.active ? 'ON CALENDAR' : 'RETIRED'} />
        </div>
        {d.notable && <div className="modal-bio">{d.notable}</div>}
      </div>
      <div className="modal-image-col">
        {mapKey
          ? <MiniTrackMap mapKey={mapKey} />
          : <div className="modal-track-placeholder">HISTORIC CIRCUIT<br/>NO DATA</div>
        }
        <div className="modal-image-label">TRACK LAYOUT</div>
      </div>
    </div>
  )
}

function HistoryDetail({ d }) {
  return (
    <>
      <div className="modal-grid">
        <Row label="ERA"   value={d.era} />
        <Row label="YEARS" value={d.years} />
      </div>
      <div className="modal-bio">{d.summary}</div>
      {d.key_events?.length > 0 && (
        <>
          <div className="modal-label" style={{ marginTop: 12 }}>KEY EVENTS</div>
          <ul style={{ marginTop: 6, paddingLeft: 16, color: 'var(--text)', fontSize: 12, lineHeight: 1.8 }}>
            {d.key_events.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </>
      )}
    </>
  )
}
