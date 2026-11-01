import moonKatana from '../moon-katana.svg';

export function Header() {
  return (
    <header>
      <a className="brand" href="./">
        skillissue<span>.gg</span>
      </a>
      <nav aria-label="Main navigation">
        <a href="#challenge">Create a record</a>
        <a href="#rules">How it works</a>
      </nav>
    </header>
  );
}

export function Hero() {
  return (
    <section className="hero">
      <div className="hero-copy">
        <p className="eyebrow">FOR THE ONES WHO DIDN’T GIVE UP</p>
        <h1>
          You fell.<br />
          You rose.<br />
          <em>You prevailed.</em>
        </h1>
        <p className="intro">
          Some victories deserve more than a screenshot.<br />
          Turn your Sekiro clear into a record worth sharing.
        </p>
        <a className="hero-link" href="#challenge">
          Record your victory <span>↘</span>
        </a>
      </div>
      <div className="art" aria-hidden="true">
        <img src={moonKatana} alt="" className="moon-katana" />
        <span className="art-caption">HESITATION IS DEFEAT.</span>
      </div>
      <div className="hero-foot">
        <span>01 / SEKIRO: SHADOWS DIE TWICE</span>
        <span>YOUR RUN. YOUR STORY.</span>
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer>
      <a className="brand" href="./">
        skillissue<span>.gg</span>
      </a>
      <p>
        Unofficial fan project. Not affiliated with FromSoftware or Activision.{' '}
        <a href="privacy.html">Privacy</a>
      </p>
      <span>BUILT FOR THE CLIMB.</span>
    </footer>
  );
}