const radar = [
  ["NIFTY", "CE", "ARMED", "74", "68", "High"],
  ["ICICI BANK", "CE", "WATCH", "67", "61", "High"],
  ["BANKNIFTY", "—", "NO EDGE", "48", "42", "Low"],
  ["USDINR", "PE", "BLOCKED", "62", "58", "Medium"],
];

export default function Home() {
  return (
    <main>
      <header>
        <div><strong>DANTE X</strong><span> MARKET INTELLIGENCE</span></div>
        <div className="live">● DEMO · SHADOW MODE · NO LIVE SIGNALS</div>
      </header>

      <nav><b>RADAR</b><span>FOCUS</span><span>LIVE TRADE</span><span>EVENTS</span><span>LAB</span></nav>

      <section className="hero">
        <div>
          <small>TOP OPPORTUNITY</small>
          <h1>NIFTY · CE <em>ARMED</em></h1>
          <p>Trigger is fixed until fired, explicitly cancelled, or expired.</p>
        </div>
        <div className="metrics">
          <Metric label="Live confirmation" value="74" />
          <Metric label="Path match" value="68" />
          <Metric label="Potential left" value="HIGH" />
          <Metric label="Probability" value="UNCALIBRATED" />
        </div>
      </section>

      <section className="grid">
        <article>
          <h2>Opportunity Radar</h2>
          <table>
            <thead><tr><th>Market</th><th>Side</th><th>Status</th><th>Confirm</th><th>Path</th><th>Potential</th></tr></thead>
            <tbody>{radar.map((r) => <tr key={r[0]}>{r.map((v, i) => <td key={i}>{v}</td>)}</tr>)}</tbody>
          </table>
          <p className="demo">Illustrative shadow data — never presented as live market data.</p>
        </article>

        <article className="plan">
          <h2>Exact Execution Plan</h2>
          <dl>
            <dt>CONTRACT</dt><dd>Awaiting live provider</dd>
            <dt>UNDERLYING TRIGGER</dt><dd>—</dd>
            <dt>PREMIUM TRIGGER</dt><dd>—</dd>
            <dt>ENTRY</dt><dd>—</dd>
            <dt>STOP / INVALIDATION</dt><dd>—</dd>
            <dt>T1 / T2</dt><dd>— / —</dd>
            <dt>QUANTITY</dt><dd>Risk engine</dd>
            <dt>NET R:R</dt><dd>Required</dd>
          </dl>
        </article>
      </section>

      <section className="evidence">
        <h2>Evidence Stack</h2>
        <div><Chip text="PRICE RESPONSE" /><Chip text="STRUCTURE" /><Chip text="BREADTH" /><Chip text="OPTION RESPONSE" /><Chip text="OI / IV" /><Chip text="CATALYST RESPONSE" /></div>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="metric"><small>{label}</small><strong>{value}</strong></div>;
}
function Chip({ text }: { text: string }) { return <span className="chip">{text}</span>; }
