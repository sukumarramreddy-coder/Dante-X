import LearningPanel from "./learning-panel";

export default function Home() {
  return <main>
    <header>
      <div><strong>DANTE X</strong><span> LEARNING & VALIDATION</span></div>
      <div className="live">READ-ONLY · NO AUTOMATIC ORDERS</div>
    </header>
    <LearningPanel />
  </main>;
}
